import os.path
from flask import Flask, Response


app = Flask(__name__)
app.config.from_object(__name__)


def root_dir():
    return os.path.abspath(os.path.dirname(__file__) + "/docs/")


def get_file(filename):
    try:
        src = os.path.join(root_dir(), filename)
        return open(src).read()
    except IOError as exc:
        return str(exc)


@app.route("/", methods=["GET"])
def metrics():
    content = get_file("_layouts/default.html")
    content = (
        content.replace("{{ site.baseurl }}", "http://127.0.0.1:5000")
        .replace("{%", "<!--")
        .replace("%}", "-->")
    )
    return Response(content, mimetype="text/html")


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def get_resource(path):
    mimetypes = {
        ".css": "text/css",
        ".html": "text/html",
        ".js": "application/javascript",
    }
    complete_path = os.path.join(root_dir(), path)
    ext = os.path.splitext(path)[1]
    mimetype = mimetypes.get(ext, "text/html")
    content = get_file(complete_path)
    return Response(content, mimetype=mimetype)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
