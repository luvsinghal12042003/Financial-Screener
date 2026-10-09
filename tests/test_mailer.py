import unittest
from backend.services.mailer import is_valid_email, build_email_content, send_portal_access_email, get_subscribers_list
from fastapi.testclient import TestClient
from backend.main import app


class TestMailerService(unittest.TestCase):
    def test_email_validation(self):
        self.assertTrue(is_valid_email("user@example.com"))
        self.assertTrue(is_valid_email("analyst.smith@hedgefund.co.in"))
        self.assertTrue(is_valid_email("trader+crypto1@sub.finance.org"))

        self.assertFalse(is_valid_email(""))
        self.assertFalse(is_valid_email("notanemail"))
        self.assertFalse(is_valid_email("user@"))
        self.assertFalse(is_valid_email("@domain.com"))
        self.assertFalse(is_valid_email(None))

    def test_email_content_builder(self):
        email = "investor@fintech.com"
        portal_link = "http://127.0.0.1:8000/?access=granted"
        subject, plain, html = build_email_content(email, portal_link)

        self.assertIn("Equity Finance Screener", subject)
        self.assertIn(portal_link, plain)
        self.assertIn(portal_link, html)
        self.assertIn("1-Second Price Streaming", plain)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn(email, html)

    def test_send_portal_access_email_simulation(self):
        email = "test.user@portal.org"
        result = send_portal_access_email(email, base_url="http://127.0.0.1:8000")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["email"], email)
        self.assertIn("http://127.0.0.1:8000/?access=granted", result["portal_link"])
        self.assertIn(result["delivery_mode"], ["demo_simulated", "smtp"])

        # Check recorded subscriber
        subscribers = get_subscribers_list()
        self.assertTrue(any(s["email"] == email for s in subscribers))

    def test_send_portal_access_email_invalid(self):
        with self.assertRaises(ValueError):
            send_portal_access_email("invalid-email-address")


class TestLaunchEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_launch_page_served(self):
        response = self.client.get("/launch")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Direct Access to Institutional Equity Intelligence", response.text)

    def test_send_portal_link_api_success(self):
        response = self.client.post("/api/send-portal-link", json={"email": "client@capital.com"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["email"], "client@capital.com")
        self.assertIn("portal_link", data)

    def test_send_portal_link_api_invalid_email(self):
        response = self.client.post("/api/send-portal-link", json={"email": "not-a-valid-email"})
        self.assertEqual(response.status_code, 400)

    def test_get_launch_subscribers(self):
        response = self.client.get("/api/launch-subscribers")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("subscribers", data)
        self.assertIsInstance(data["subscribers"], list)


if __name__ == "__main__":
    unittest.main()
