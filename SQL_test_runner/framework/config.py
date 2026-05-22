import configparser
import os


def load_config(config_path):
    config = configparser.ConfigParser()
    config.read(config_path)

    db = config["database"]
    settings = config["settings"] if "settings" in config else {}
    global_cfg = config["global"] if "global" in config else {}

    config_dir = os.path.dirname(os.path.abspath(config_path))
    raw_setup_dir = global_cfg.get("setup_dir", "").strip()
    setup_dir = os.path.join(config_dir, raw_setup_dir) if raw_setup_dir else None

    return {
        "host": db.get("host", "localhost"),
        "port": int(db.get("port", 3306)),
        "user": db.get("user"),
        "password": db.get("password"),
        "database": db.get("database"),
        "float_precision": int(settings.get("float_precision", 6)),
        "global_setup_dir": setup_dir,
    }
