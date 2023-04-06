from rq.job import get_current_job

_counter = 0


def arg_callable():
    global _counter
    _counter += 1
    return _counter


def test_job():
    return 1 + 1


def test_args_kwargs(*args, **kwargs):
    func = "test_args_kwargs({})"
    args_list = [repr(arg) for arg in args]
    kwargs_list = [f'{k}={v}' for (k, v) in kwargs.items()]
    return func.format(', '.join(args_list + kwargs_list))


test_non_callable = 'I am a teapot'


def failing_job():
    raise ValueError


def access_self():
    return get_current_job().id
