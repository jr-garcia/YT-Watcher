from .youtube_dl.utils import YoutubeDLError, DownloadError

import urllib3 as ulib
import certifi

MAXTRIES = 5


def download(url, retryNumber=0):
    headers = {'user-agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:54.0) Gecko/20100101 Firefox/54.0'}
    host = ulib.get_host(url)
    fullhost = host[0] + '://' + host[1]
    con = ulib.connection_from_url(fullhost, cert_reqs='CERT_REQUIRED', ca_certs=certifi.where(),
                                   retries=False)
    file = url.replace(fullhost, '', 1)
    try:
        result = con.request('GET', file, headers=headers)
        status = result.status
        if 200 <= status < 300:
            return result.data
        elif 399 < status < 500:
            raise DownloadError('Error {}'.format(status))
        elif status in result.REDIRECT_STATUSES:
            if retryNumber >= MAXTRIES:
                raise DownloadError('Max retries reached.')
            return download(result.headers['location'], retryNumber+1)
    except ulib.exceptions.HTTPError as err:
        raise DownloadError('URL: {} error:{}'.format(url, err))
    except Exception:
        raise
