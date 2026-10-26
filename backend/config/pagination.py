from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """50 results per page; the frontend may ask for more with ?page_size=100 (max 500)."""

    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500
