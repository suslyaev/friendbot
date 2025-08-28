class DisableHostCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Отключаем проверку хоста для внутренних запросов
        if 'django_app' in request.get_host():
            request.META['HTTP_HOST'] = 'localhost:8000'
        return self.get_response(request)

    def process_request(self, request):
        # Альтернативный способ отключения проверки хоста
        if 'django_app' in request.get_host():
            request.META['HTTP_HOST'] = 'localhost:8000'
        return None
