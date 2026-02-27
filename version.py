"""
Version configuration for DouYin_AutoClik
"""
__version__ = "1.0.0"
__release_date__ = "2026-02-27"
__app_name__ = "DouYin_AutoClik"

def get_version_info():
    """Get version information as dictionary"""
    return {
        "version": __version__,
        "release_date": __release_date__,
        "app_name": __app_name__
    }

def get_zip_name():
    """Generate release zip file name"""
    return f"{__app_name__}-v{__version__}-win64.zip"
