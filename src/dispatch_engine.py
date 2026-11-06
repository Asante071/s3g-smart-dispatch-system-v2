from services.dispatch_recommendation_service import DispatchRecommendationService


class DispatchEngine:
    """Compatibility facade for the transparent dispatch recommendation service."""

    def __init__(self, recommendation_service=None):
        self.recommendation_service = recommendation_service or DispatchRecommendationService()

    def recommend_engineer(self, engineers):
        """Return the top eligible engineer, or None when no-one is available."""
        engineers = list(engineers)
        recommendation = self.recommendation_service.recommend(engineers)["recommendation"]
        if recommendation is None:
            return None
        return next(
            engineer
            for engineer in engineers
            if engineer.id == recommendation["id"]
        )

    def rank_engineers(self, engineers):
        return self.recommendation_service.recommend(engineers)
