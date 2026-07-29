"""
Locust stress test for the Self-Improving AI API.

Usage:
    locust -f tests/stress/locustfile.py --host http://localhost:8000
"""

from locust import HttpUser, task, between


class SelfImprovingAIUser(HttpUser):
    """Simulated user traffic for the Self-Improving AI API."""

    wait_time = between(0.5, 2.0)

    @task(3)
    def health_check(self):
        self.client.get("/health")

    @task(2)
    def system_status(self):
        self.client.get("/status")

    @task(1)
    def list_experiments(self):
        self.client.get("/api/v1/experiments/")

    @task(1)
    def get_leaderboard(self):
        self.client.get("/api/v1/evaluations/leaderboard")

    @task(1)
    def list_agents(self):
        self.client.get("/api/v1/agents/")

    @task(1)
    def get_failure_rate(self):
        self.client.get("/api/v1/observations/failure-rate")

    @task(1)
    def record_observation(self):
        self.client.post(
            "/api/v1/observations/?observation_type=user_interaction&session_id=stress&success=true"
        )
