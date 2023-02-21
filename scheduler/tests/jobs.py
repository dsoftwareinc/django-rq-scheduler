from django_rq import job as jobdecorator


@jobdecorator
def test_job():
    return 1 + 1


@jobdecorator
def test_args_kwargs(*args, **kwargs):
    func = "test_args_kwargs({})"
    args_list = [repr(arg) for arg in args]
    kwargs_list = [f'{k}={v}' for (k, v) in kwargs.items()]
    return func.format(', '.join(args_list + kwargs_list))


test_non_callable = 'I am a teapot'
