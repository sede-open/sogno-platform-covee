import venv

builder = venv.EnvBuilder(with_pip=True)
builder.create("./covee_env")
