import mimetypes
import io
import os

from .utils import fetch_from_list_request, request
from .upload import CustomResumableUpload


class File:
    base_path = '/storage'

    def __init__(self, name, path, metadata, **extra_attributes):
        """The File class represents files stored in Dymaxion Labs.

        Files are owned by the authenticated user.

        Args:
            name: file name
            path: file path
            metadata: file metadata
            extra_attributes: extra attributes from API endpoint

        """
        self.name = name
        self.path = path
        self.metadata = metadata
        self.tailing_job = None
        self.extra_attributes = extra_attributes

    @classmethod
    def all(cls, path="*"):
        response = request('get',
                           '/storage/files/?path={path}'.format(path=path))
        return [File(**attrs) for attrs in response]

    @classmethod
    def get(cls, path):
        """Get a specific File in +path+"""
        attrs = request(
            'get',
            '{base_path}/file/?path={path}'.format(base_path=cls.base_path,
                                                   path=path))
        return File(**attrs['detail'])

    def delete(self):
        """Delete file"""
        request(
            'delete',
            '{base_path}/file/?path={path}'.format(base_path=self.base_path,
                                                   path=self.path))
        return True

    @classmethod
    def _resumable_url(cls, storage_path, size):
        url_path = '{base_path}/create-resumable-upload/?path={path}&size={size}'.format(
            base_path=cls.base_path, path=storage_path, size=size)
        response = request('post', url_path)
        return response

    @classmethod
    def _resumable_upload(cls, input_path, storage_path):
        chunk_size = 1024 * 1024  # 1MB
        f = open(input_path, "rb")
        stream = io.BytesIO(f.read())
        metadata = {u'name': os.path.basename(input_path)}
        res = cls._resumable_url(storage_path, os.path.getsize(input_path))
        upload = CustomResumableUpload(res['session_url'], chunk_size)
        upload.initiate(
            stream,
            metadata,
            mimetypes.MimeTypes().guess_type(input_path)[0],
            res['session_url'],
        )
        while (not upload.finished):
            upload.transmit_next_chunk()
        return cls.get(storage_path)

    @classmethod
    def _upload(cls, input_path, storage_path):
        filename = os.path.basename(input_path)
        with open(input_path, 'rb') as fp:
            data = fp.read()
        path = '{base_path}/upload/'.format(base_path=cls.base_path)
        response = request(
            'post',
            path,
            body={'path': storage_path},
            files={'file': data},
        )
        return File(**response['detail'])

    @classmethod
    def upload(cls, input_path, storage_path):
        """Upload a file to storage

        Args:
            input_path -- path to local file
            storage_path -- destination path

        Raises:
            FileNotFoundError: Path
        """
        if (os.path.getsize(input_path) > 1024 * 1024):
            file = cls._resumable_upload(input_path, storage_path)
        else:
            file = cls._upload(input_path, storage_path)
        return file

    def download(self, output_dir="."):
        """Download file and save it to +output_dir+

        If +output_dir+ does not exist, it will be created.

        Args:
            output_dir: path to store file
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        path = '{base_path}/download/?path={path}'.format(
            base_path=self.base_path, path=self.path)
        content = request('get', path, binary=True, parse_response=False)
        output_file = os.path.join(output_dir, self.name)
        with open(output_file, 'wb') as f:
            f.write(content)

    def tailing(self):
        from .tasks import Task
        response = request('post',
                           '/estimators/start_tailing_job/',
                           body={'path': self.path})
        self.tailing_job = Task._from_attributes(response['detail'])
        return self.tailing_job

    def __repr__(self):
        return "<File name={name!r}".format(name=self.name)
