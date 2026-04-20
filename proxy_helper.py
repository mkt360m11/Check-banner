import os
import zipfile

def create_proxy_extension(proxy_str):
    """
    Creates a temporary Chrome extension to handle proxy authentication.
    proxy_str format: ip:port:user:pass or ip:port
    Returns the path to the directory containing the extension.
    """
    parts = proxy_str.split(':')
    if len(parts) < 2:
        return None
        
    ip = parts[0]
    port = parts[1]
    user = parts[2] if len(parts) > 2 else ""
    pw = parts[3] if len(parts) > 3 else ""

    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        },
        "minimum_chrome_version":"22.0.0"
    }
    """

    background_js = """
    var config = {
            mode: "fixed_servers",
            rules: {
              singleProxy: {
                scheme: "http",
                host: "%s",
                port: parseInt(%s)
              },
              bypassList: ["localhost"]
            }
          };

    chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

    function callbackFn(details) {
        return {
            authCredentials: {
                username: "%s",
                password: "%s"
            }
        };
    }

    chrome.webRequest.onAuthRequired.addListener(
                callbackFn,
                {urls: ["<all_urls>"]},
                ['blocking']
    );
    """ % (ip, port, user, pw)

    plugin_dir = os.path.join(os.getcwd(), 'proxy_auth_plugin')
    if not os.path.exists(plugin_dir):
        os.makedirs(plugin_dir)

    with open(os.path.join(plugin_dir, "manifest.json"), "w") as f:
        f.write(manifest_json)

    with open(os.path.join(plugin_dir, "background.js"), "w") as f:
        f.write(background_js)

    return plugin_dir
