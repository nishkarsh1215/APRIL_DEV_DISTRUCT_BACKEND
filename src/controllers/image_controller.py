from flask import Response, abort
from flask_restx import Namespace, Resource
import gridfs
from mongoengine.connection import get_db
from bson import ObjectId

image_ns = Namespace('images', description="Image retrieval endpoints")

@image_ns.route('/<string:image_id>')
class ImageResource(Resource):
    def get(self, image_id):
        db = get_db()
        fs = gridfs.GridFS(db, collection='image_files')
        try:
            grid_out = fs.get(ObjectId(image_id))
        except Exception:
            abort(404)
        return Response(grid_out.read(), mimetype=grid_out.content_type)
