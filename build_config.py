"""
Build configuration utilities
Handle paths for both development and packaged environments
"""
import os
import sys

def is_frozen():
    """Check if running as frozen exe"""
    return getattr(sys, 'frozen', False)

def get_base_path():
    """Get base path for resources (PyInstaller temp path)"""
    if is_frozen():
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_app_path():
    """Get application directory (where exe is located)"""
    if is_frozen():
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_data_path():
    """Get data directory path"""
    app_path = get_app_path()
    data_path = os.path.join(app_path, "data")
    if not os.path.exists(data_path):
        os.makedirs(data_path)
    return data_path

def get_config_path():
    """Get config file path"""
    data_path = get_data_path()
    return os.path.join(data_path, "config.json")

def get_default_config_path():
    """Get default config template path"""
    base_path = get_base_path()
    return os.path.join(base_path, "config.json.default")

def get_state_path():
    """Get state file path"""
    data_path = get_data_path()
    return os.path.join(data_path, "state.json")

def get_logs_path():
    """Get logs directory path"""
    data_path = get_data_path()
    logs_path = os.path.join(data_path, "logs")
    if not os.path.exists(logs_path):
        os.makedirs(logs_path)
    return logs_path

def get_comment_history_path():
    """Get comment history file path"""
    data_path = get_data_path()
    return os.path.join(data_path, "comment_history.json")
