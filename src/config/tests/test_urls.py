from django.test import SimpleTestCase


class TestsRootUrl(SimpleTestCase):
    """
    Tests for the project root URL.
    """

    def test_root_url_redirects_to_shop(self):
        """
        The project root redirects users to the storefront.
        """

        response = self.client.get("/")

        self.assertRedirects(
            response=response,
            expected_url="/shop/",
            status_code=302,
            fetch_redirect_response=False,
        )