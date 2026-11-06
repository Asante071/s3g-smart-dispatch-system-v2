from services.dispatch_recommendation_service import DispatchRecommendationService
from src.dispatch_engine import DispatchEngine
from src.engineer import Engineer


def test_scores_are_normalised_over_supported_weights_and_rank_lowest_workload_first():
    result = DispatchRecommendationService().recommend([
        Engineer(1, "Busy", 8, True),
        Engineer(2, "Free", 2, True),
    ])

    assert result["approved_weights"] == {
        "technical_expertise": 35,
        "current_workload": 25,
        "historical_sla_success": 15,
        "geographical_proximity": 15,
        "real_time_availability": 5,
        "estimated_travel_time": 5,
    }
    assert result["active_weight_total"] == 30
    assert result["ranking"][0]["name"] == "Free"
    assert result["ranking"][0]["score"] == 100
    assert result["ranking"][1]["score"] == round(5 / 30 * 100, 2)


def test_unavailable_engineers_are_ineligible_and_not_ranked():
    result = DispatchRecommendationService().recommend([
        Engineer(1, "Unavailable", 0, False),
        Engineer(2, "Available", 5, True),
    ])

    assert [candidate["name"] for candidate in result["ranking"]] == ["Available"]
    assert result["ineligible_engineers"] == [
        {"id": 1, "name": "Unavailable", "reason": "unavailable"}
    ]


def test_equal_workloads_receive_equal_scores_with_deterministic_tie_breaking():
    result = DispatchRecommendationService().recommend([
        Engineer(2, "Zoe", 3, True),
        Engineer(1, "Ava", 3, True),
    ])

    assert [candidate["name"] for candidate in result["ranking"]] == ["Ava", "Zoe"]
    assert [candidate["score"] for candidate in result["ranking"]] == [100, 100]


def test_no_eligible_engineers_returns_no_recommendation():
    result = DispatchRecommendationService().recommend([Engineer(1, "Away", 0, False)])

    assert result["recommendation"] is None
    assert result["ranking"] == []
    assert result["unavailable_criteria"] == [
        "technical_expertise",
        "historical_sla_success",
        "geographical_proximity",
        "estimated_travel_time",
    ]


def test_dispatch_engine_keeps_returning_the_engineer_object_for_legacy_callers():
    recommended = DispatchEngine().recommend_engineer([
        Engineer(1, "Busy", 4, True),
        Engineer(2, "Free", 1, True),
    ])

    assert isinstance(recommended, Engineer)
    assert recommended.name == "Free"


def test_expertise_and_persisted_sla_outcomes_are_weighted_and_normalised():
    result = DispatchRecommendationService().recommend([
        Engineer(1, "Expert", 4, True, ["network", "linux"], [{"sla_met": True}, {"sla_met": True}]),
        Engineer(2, "Free", 1, True, ["network"], [{"sla_met": False}, {"sla_met": False}]),
    ], required_skills=["network", "linux"])

    assert result["active_weight_total"] == 80
    assert result["ranking"][0]["name"] == "Expert"
    assert result["ranking"][0]["score_breakdown"]["technical_expertise"]["normalised_score"] == 1
    assert result["ranking"][0]["score_breakdown"]["historical_sla_success"]["normalised_score"] == 1
    assert result["ranking"][1]["score_breakdown"]["technical_expertise"]["normalised_score"] == 0.5


def test_no_history_is_neutral_only_when_other_engineer_has_real_history():
    result = DispatchRecommendationService().recommend([
        Engineer(1, "New", 1, True, ["network"]),
        Engineer(2, "Established", 1, True, ["network"], [{"sla_met": True}]),
    ], incident_category="network")

    new = next(item for item in result["ranking"] if item["name"] == "New")
    assert new["score_breakdown"]["historical_sla_success"]["normalised_score"] == 0.5
    assert new["score_breakdown"]["historical_sla_success"]["no_history_policy"] == "neutral 0.5"


def test_sla_is_inactive_when_no_engineer_has_recorded_outcomes():
    result = DispatchRecommendationService().recommend([Engineer(1, "New", 1, True)], required_skills=["network"])

    assert result["active_weight_total"] == 65
    assert "historical_sla_success" in result["unavailable_criteria"]


def test_proximity_uses_haversine_straight_line_distance_and_favours_nearer_engineer():
    result = DispatchRecommendationService().recommend([
        Engineer(1, "Far", 2, True, latitude=-26.2041, longitude=28.0473),
        Engineer(2, "Near", 2, True, latitude=-26.1050, longitude=28.0560),
    ], incident_latitude=-26.1076, incident_longitude=28.0567)

    assert result["active_weight_total"] == 45
    assert result["recommendation"]["name"] == "Near"
    assert result["recommendation"]["score_breakdown"]["geographical_proximity"] == {
        "raw_value": result["recommendation"]["score_breakdown"]["geographical_proximity"]["raw_value"],
        "unit": "km straight-line", "calculation": "Haversine", "normalised_score": 1.0,
        "weight": 15, "evidence_status": "usable",
    }
    assert result["recommendation"]["score_breakdown"]["geographical_proximity"]["raw_value"] > 0
    assert "estimated_travel_time" in result["unavailable_criteria"]


def test_missing_engineer_coordinates_do_not_fabricate_a_proximity_score():
    result = DispatchRecommendationService().recommend([
        Engineer(1, "Located", 2, True, latitude=-26.1050, longitude=28.0560),
        Engineer(2, "Unknown", 2, True),
    ], incident_latitude=-26.1076, incident_longitude=28.0567)

    unknown = next(candidate for candidate in result["ranking"] if candidate["name"] == "Unknown")
    assert result["active_weight_total"] == 45
    assert unknown["active_weight_total"] == 30
    assert unknown["score_breakdown"]["geographical_proximity"]["normalised_score"] is None
    assert unknown["score_breakdown"]["geographical_proximity"]["evidence_status"] == "missing_engineer_coordinates"
