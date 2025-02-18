import venv

builder = venv.EnvBuilder(with_pip=True)
builder.create("./venv_ext")
