import main


def test_parse_args_defaults_to_one_click():
    args = main.parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    # 一键启动：默认带上前端、自动拉起 EVA
    assert args.with_frontend is True
    assert args.skip_eva is False
    assert args.eva_dir == ""


def test_parse_args_accepts_frontend_flag():
    args = main.parse_args(["--with-frontend", "--port", "8010"])
    assert args.with_frontend is True
    assert args.port == 8010


def test_parse_args_accepts_eva_options():
    args = main.parse_args(["--eva-dir", "D:/eva", "--skip-eva"])
    assert args.eva_dir == "D:/eva"
    assert args.skip_eva is True


def test_build_frontend_command_uses_resolved_npm_executable():
    command = main.build_frontend_command(5174, npm_executable="C:/node/npm.cmd")
    assert command == ["C:/node/npm.cmd", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5174"]
