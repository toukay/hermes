class PaginationSession:
    def __init__(self, message, headers, pages):
        self.message = message
        self.headers = headers
        self.pages = pages
        self.current_page = 0