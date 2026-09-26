"""Bounded GET-only reader for the company's explicitly shared OneDrive sources.

Microsoft REST reference: https://learn.microsoft.com/en-us/sharepoint/dev/sp-add-ins/working-with-folders-and-files-with-rest
No upload, checkout, save, formula calculation or permission-changing API exists here.
"""
import re
from urllib.parse import urlsplit, urljoin, unquote
import requests
from .sales_bi_parser import WorkbookError, filename_month


class SourceError(WorkbookError):
    pass


def validate_url(url, *, share=False):
    p = urlsplit(url)
    host = (p.hostname or '').lower()
    allowed = host in ('1drv.ms', 'onedrive.live.com') or (not share and host.endswith('.files.1drv.com'))
    if p.scheme != 'https' or not allowed or p.username or p.password or p.port not in (None, 443):
        raise SourceError('Use um link de compartilhamento HTTPS do OneDrive.')
    return url


def validate_root(root):
    if not re.fullmatch(r'/personal/[a-fA-F0-9]{16}/Documents/[^\x00-\x1f?#]+', root) or any(s in ('.', '..') for s in unquote(root).split('/')):
        raise SourceError('Caminho da pasta OneDrive inválido.')
    return root.rstrip('/')


class OneDriveReader:
    def __init__(self, current_url, archive_url, archive_root):
        self.current_url = validate_url(current_url, share=True)
        self.archive_url = validate_url(archive_url, share=True)
        self.root = validate_root(archive_root)
        self.site = 'https://onedrive.live.com' + '/'.join(self.root.split('/')[:3])
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'ERP-Eleven-SalesViewer/1.0'

    def close(self):
        self.session.close()

    def get(self, url, *, limit=20_000_000, params=None):
        # Validate every redirect BEFORE the next request. Sharing URLs are never logged.
        try:
            for _ in range(8):
                validate_url(url)
                with self.session.get(url, params=params, timeout=(10, 40), allow_redirects=False, stream=True,
                                      headers={'Accept': 'application/json;odata=nometadata'}) as response:
                    params = None
                    if response.status_code in (301, 302, 303, 307, 308):
                        url = urljoin(url, response.headers.get('Location', ''))
                        continue
                    if response.status_code != 200:
                        raise SourceError(f'OneDrive indisponível (HTTP {response.status_code}). Confira o compartilhamento das fontes.')
                    output = bytearray()
                    for chunk in response.iter_content(65536):
                        output.extend(chunk)
                        if len(output) > limit:
                            raise SourceError('A fonte excede o tamanho permitido para leitura.')
                    return bytes(output)
            raise SourceError('Não foi possível resolver o link do OneDrive.')
        except requests.RequestException:
            raise SourceError('Não foi possível ler o OneDrive. A última leitura válida foi preservada.') from None

    def current(self):
        return self.get(self.current_url, params={'download': '1'})

    def in_scope(self, path):
        if not path.startswith(self.root + '/') or not unquote(path).startswith(unquote(self.root) + '/') or any(s in ('.', '..') for s in unquote(path).split('/')):
            raise SourceError('Item fora da pasta de histórico configurada.')
        return path

    def listing(self, path, kind):
        import json
        if path != self.root:
            self.in_scope(path)
        escaped = path.replace("'", "''")
        url = self.site + f"/_api/web/GetFolderByServerRelativeUrl('{escaped}')/{kind}"
        params = {'$select': 'Name,ServerRelativeUrl,UniqueId' + (',TimeLastModified,Length' if kind == 'Files' else ''), '$top': '200'}
        items = []
        for _ in range(10):
            try:
                data = json.loads(self.get(url, params=params, limit=2_000_000))
            except (ValueError, TypeError):
                raise SourceError('A pasta não retornou uma lista de arquivos. Confira o link compartilhado.') from None
            batch = data.get('value')
            if not isinstance(batch, list):
                raise SourceError('Lista de arquivos do OneDrive inválida.')
            items.extend(batch)
            if len(items) > 600:
                raise SourceError('A pasta excede o limite de 600 itens.')
            next_url = data.get('@odata.nextLink') or data.get('odata.nextLink')
            if not next_url:
                return items
            url = urljoin(self.site + '/', next_url)
            if not url.startswith(self.site + '/_api/'):
                raise SourceError('Paginação fora da fonte configurada.')
            params = None
        raise SourceError('Lista de arquivos excede o limite de páginas.')

    def archive(self):
        self.get(self.archive_url, limit=5_000_000)
        files = []
        for folder in self.listing(self.root, 'Folders'):
            name = str(folder.get('Name', ''))
            if not re.fullmatch(r'20\d{2}', name):
                continue
            for f in self.listing(self.in_scope(folder['ServerRelativeUrl']), 'Files'):
                if str(f.get('Name', '')).lower().endswith('.xlsx'):
                    path = self.in_scope(f['ServerRelativeUrl'])
                    if int(f.get('Length') or 0) > 20_000_000:
                        raise SourceError('Uma planilha histórica excede 20 MB.')
                    files.append({'path': path, 'filename': f['Name'], 'year': int(name), 'month': filename_month(f['Name']),
                                  'version': str(f.get('TimeLastModified') or '') + ':' + str(f.get('Length') or ''),
                                  'remote_id': str(f['UniqueId'])})
                    if len(files) > 600:
                        raise SourceError('Histórico excede o limite de 600 planilhas.')
        return files

    def download(self, path):
        path = self.in_scope(path).replace("'", "''")
        return self.get(self.site + f"/_api/web/GetFileByServerRelativeUrl('{path}')/$value")
