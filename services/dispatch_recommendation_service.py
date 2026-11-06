"""Transparent, capability-aware engineer dispatch recommendations.

The domain model currently contains only workload and availability.  The
approved dispatch-policy weights are kept intact here, but unavailable inputs
are never fabricated: the score is normalised over the supported criteria and
the API tells its caller which criteria could not be evaluated.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Iterable
from services.routing_service import RoutingService


class DispatchRecommendationService:
    """Rank available engineers using the fields that the current model has."""

    def __init__(self, routing_service=None):
        self.routing_service = routing_service

    APPROVED_WEIGHTS = {
        "technical_expertise": 35,
        "current_workload": 25,
        "historical_sla_success": 15,
        "geographical_proximity": 15,
        "real_time_availability": 5,
        "estimated_travel_time": 5,
    }
    SUPPORTED_CRITERIA = ("current_workload", "real_time_availability")
    UNAVAILABLE_CRITERIA = ("geographical_proximity", "estimated_travel_time")

    def recommend(self, engineers: Iterable[object], required_skills=None, incident_category=None,
                  incident_latitude=None, incident_longitude=None) -> dict:
        """Return an explainable ranking without inventing absent data.

        Availability is an eligibility gate.  Workload is min-max normalised
        among eligible engineers, with lower workload producing a higher score.
        When all eligible engineers have the same workload, each receives the
        same workload score of 1.0 rather than an arbitrary advantage.
        """
        engineers = list(engineers)
        eligible = [engineer for engineer in engineers if engineer.availability]
        ineligible = [engineer for engineer in engineers if not engineer.availability]

        requested_skills = self._normalise_skills(required_skills or ([incident_category] if incident_category else []))
        active_criteria = list(self.SUPPORTED_CRITERIA)
        if requested_skills:
            active_criteria.append("technical_expertise")
        if any(getattr(engineer, "completed_assignments", []) for engineer in eligible):
            active_criteria.append("historical_sla_success")
        incident_coordinates = self._coordinate_pair(incident_latitude, incident_longitude)
        distances = {}
        if incident_coordinates:
            for engineer in eligible:
                engineer_coordinates = self._coordinate_pair(
                    getattr(engineer, "latitude", None), getattr(engineer, "longitude", None)
                )
                if engineer_coordinates:
                    distances[engineer.id] = self._haversine_km(incident_coordinates, engineer_coordinates)
        if distances:
            active_criteria.append("geographical_proximity")
        travel_routes = {}
        if incident_coordinates and self.routing_service is not None:
            for engineer in eligible:
                engineer_coordinates = self._coordinate_pair(
                    getattr(engineer, "latitude", None),
                    getattr(engineer, "longitude", None)
                )
                if engineer_coordinates:
                    route = self.routing_service.get_route(
                        {
                            "latitude": incident_coordinates[0],
                            "longitude": incident_coordinates[1],
                        },
                        {
                            "latitude": engineer_coordinates[0],
                            "longitude": engineer_coordinates[1],
                        },
                    )
                    if route and route.get("status") == "success":
                        travel_routes[engineer.id] = route

        if travel_routes:
            active_criteria.append("estimated_travel_time")
        active_weight_total = sum(self.APPROVED_WEIGHTS[criterion] for criterion in active_criteria)
        base = self._response_metadata(active_weight_total, active_criteria)
        base["ineligible_engineers"] = [
            {"id": engineer.id, "name": engineer.name, "reason": "unavailable"}
            for engineer in ineligible
        ]

        if not eligible:
            base.update({"recommendation": None, "ranking": []})
            return base

        workloads = [engineer.workload for engineer in eligible]
        lowest_workload = min(workloads)
        highest_workload = max(workloads)
        nearest_distance = min(distances.values()) if distances else None
        farthest_distance = max(distances.values()) if distances else None

        fastest_time = min(
            route["duration_minutes"] for route in travel_routes.values()
        ) if travel_routes else None

        slowest_time = max(
            route["duration_minutes"] for route in travel_routes.values()
        ) if travel_routes else None

        ranking = []
        for engineer in eligible:
            workload_score = self._normalise_workload(
                engineer.workload, lowest_workload, highest_workload
            )
            availability_score = 1.0
            expertise_score = self._expertise_score(engineer, requested_skills)
            sla_score, history_count = self._sla_score(engineer)
            scores = {"current_workload": workload_score, "real_time_availability": availability_score,
                      "technical_expertise": expertise_score, "historical_sla_success": sla_score}
            candidate_criteria = list(active_criteria)
            distance = distances.get(engineer.id)
            route = travel_routes.get(engineer.id)
            if "estimated_travel_time" in candidate_criteria:
                if route is None:
                    candidate_criteria.remove("estimated_travel_time")
                else:
                    scores["estimated_travel_time"] = self._normalise_distance(
                        route["duration_minutes"], fastest_time, slowest_time
                    )
            if "geographical_proximity" in candidate_criteria:
                if distance is None:
                    candidate_criteria.remove("geographical_proximity")
                else:
                    scores["geographical_proximity"] = self._normalise_distance(distance, nearest_distance, farthest_distance)
            candidate_weight_total = sum(self.APPROVED_WEIGHTS[key] for key in candidate_criteria)
            score = sum(scores[key] * self.APPROVED_WEIGHTS[key] for key in candidate_criteria) / candidate_weight_total * 100
            breakdown = {
                "estimated_travel_time": {
                    "raw_value": route["duration_minutes"] if route else None,
                    "distance_km": route["distance_km"] if route else None,
                    "provider": route["provider"] if route else None,
                    "normalised_score": round(
                        scores["estimated_travel_time"], 4
                    ) if route and "estimated_travel_time" in scores else None,
                    "weight": 5,
                },
                "current_workload": {
                    "raw_value": engineer.workload, "normalised_score": round(workload_score, 4), "weight": 25,
                },
                "real_time_availability": {
                    "raw_value": engineer.availability, "normalised_score": availability_score, "weight": 5,
                },
            }
            if "technical_expertise" in active_criteria:
                breakdown["technical_expertise"] = {
                    "raw_value": sorted(engineer.skills), "requested_skills": requested_skills,
                    "normalised_score": round(expertise_score, 4), "weight": 35,
                }
            if "historical_sla_success" in active_criteria:
                breakdown["historical_sla_success"] = {
                    "completed_assignment_count": history_count,
                    "raw_value": round(sla_score, 4) if history_count else None,
                    "normalised_score": round(sla_score, 4), "weight": 15,
                    "no_history_policy": "neutral 0.5" if not history_count else None,
                }
            if "geographical_proximity" in active_criteria:
                breakdown["geographical_proximity"] = {
                    "raw_value": round(distance, 4) if distance is not None else None,
                    "unit": "km straight-line", "calculation": "Haversine",
                    "normalised_score": round(scores["geographical_proximity"], 4) if distance is not None else None,
                    "weight": 15,
                    "evidence_status": "usable" if distance is not None else "missing_engineer_coordinates",
                }
            ranking.append(
                {
                    "id": engineer.id,
                    "name": engineer.name,
                    "workload": engineer.workload,
                    "availability": engineer.availability,
                    "score": round(score, 2),
                    "active_criteria": candidate_criteria,
                    "active_weight_total": candidate_weight_total,
                    "score_breakdown": breakdown,
                }
            )

        ranking.sort(key=lambda candidate: (-candidate["score"], candidate["name"], candidate["id"]))
        base.update({"recommendation": ranking[0], "ranking": ranking})
        return base

    def _response_metadata(self, active_weight_total: int, active_criteria: list[str]) -> dict:
        return {
            "approved_weights": self.APPROVED_WEIGHTS.copy(),
            "scoring_method": "Scores are normalised over active, evidence-supported criteria only.",
            "scoring_semantics": "Expertise is matched requested skills / requested skills. Historical SLA success is SLA-met completed assignments / completed assignments; no history is neutral 0.5 when peer history exists.",
            "active_criteria": active_criteria,
            "active_weight_total": active_weight_total,
            "unavailable_criteria": [key for key in self.APPROVED_WEIGHTS if key not in active_criteria],
        "limitations": (
                     "Geographical proximity uses Haversine straight-line distance in "
                     "kilometres when incident and engineer coordinates exist; it is not "
                     "road distance or travel time. Engineers without coordinate evidence "
                     "have proximity inactive for their individual normalised score. "
                     "Estimated travel time uses OSRM road-route duration when valid route "
                     "data is available and is inactive when routing data is unavailable. "
                     "The public OSRM demo service is intended for development and testing, "
                     "not production use. Expertise is inactive without incident "
                     "requirements; SLA success is inactive when no eligible engineer "
                     "has history."
),
        }

    @staticmethod
    def _normalise_workload(workload: float, minimum: float, maximum: float) -> float:
        if minimum == maximum:
            return 1.0
        return (maximum - workload) / (maximum - minimum)

    @staticmethod
    def _normalise_distance(distance: float, minimum: float, maximum: float) -> float:
        if minimum == maximum:
            return 1.0
        return (maximum - distance) / (maximum - minimum)

    @staticmethod
    def _coordinate_pair(latitude, longitude):
        if latitude is None or longitude is None:
            return None
        return latitude, longitude

    @staticmethod
    def _haversine_km(origin, destination):
        latitude_1, longitude_1, latitude_2, longitude_2 = map(radians, (*origin, *destination))
        a = sin((latitude_2 - latitude_1) / 2) ** 2 + cos(latitude_1) * cos(latitude_2) * sin((longitude_2 - longitude_1) / 2) ** 2
        return 2 * 6371.0088 * asin(sqrt(a))

    @staticmethod
    def _normalise_skills(skills):
        return sorted({skill.strip().lower() for skill in skills if skill and skill.strip()})

    def _expertise_score(self, engineer, requested_skills):
        if not requested_skills:
            return 0.0
        return len(set(self._normalise_skills(engineer.skills)) & set(requested_skills)) / len(requested_skills)

    @staticmethod
    def _sla_score(engineer):
        outcomes = getattr(engineer, "completed_assignments", [])
        if not outcomes:
            return 0.5, 0
        return sum(item["sla_met"] for item in outcomes) / len(outcomes), len(outcomes)
