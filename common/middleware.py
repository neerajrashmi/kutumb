import threading

_thread_locals = threading.local()

def get_current_user_id():
    """Returns the Individual_Id of the logged-in user for the current thread."""
    return getattr(_thread_locals, 'user_id', None)

class CurrentUserMiddleware:
    """
    Captures the logged-in user from the HTTP request and stores
    their Individual_Id in thread-local storage for the model lifecycle.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            # User_Detail.pk / user_id is the Individual_Id (e.g. 'I0000001')
            _thread_locals.user_id = str(request.user.pk)
        else:
            _thread_locals.user_id = None

        response = self.get_response(request)

        # Clean up thread-local storage after response completes
        _thread_locals.user_id = None
        return response