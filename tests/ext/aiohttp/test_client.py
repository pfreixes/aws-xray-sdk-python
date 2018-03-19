import pytest
from aiohttp import ClientSession

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core.async_context import AsyncContext
from aws_xray_sdk.ext.util import strip_url
from aws_xray_sdk.ext.aiohttp.client import aws_xray_trace_config



# httpbin.org is created by the same author of requests to make testing http easy.
BASE_URL = 'httpbin.org'


@pytest.fixture(scope='function')
def recorder(loop):
    """
    Initiate a recorder and clear it up once has been used.
    """
    xray_recorder.configure(service='test', sampling=False, context=AsyncContext(loop=loop))
    xray_recorder.clear_trace_entities()
    yield recorder
    xray_recorder.clear_trace_entities()


async def test_ok(loop, recorder):
    xray_recorder.begin_segment('name')
    trace_config = aws_xray_trace_config()
    status_code = 200
    url = 'http://{}/status/{}?foo=bar'.format(BASE_URL, status_code)
    async with ClientSession(loop=loop, trace_configs=[trace_config]) as session:
        async with session.get(url):
            pass

    subsegment = xray_recorder.current_segment().subsegments[0]
    assert subsegment.name == strip_url(url)

    http_meta = subsegment.http
    assert http_meta['request']['url'] == url
    assert http_meta['request']['method'] == 'GET'
    assert http_meta['response']['status'] == status_code


async def test_ok_name_and_namespace(loop, recorder):
    xray_recorder.begin_segment('name')
    trace_config = aws_xray_trace_config(name='test', namespace='local')
    status_code = 200
    url = 'http://{}/status/{}?foo=bar'.format(BASE_URL, status_code)
    async with ClientSession(loop=loop, trace_configs=[trace_config]) as session:
        async with session.get(url):
            pass

    subsegment = xray_recorder.current_segment().subsegments[0]
    assert subsegment.name == 'test'
    assert subsegment.namespace == 'local'


async def test_error(loop, recorder):
    xray_recorder.begin_segment('name')
    trace_config = aws_xray_trace_config()
    status_code = 400
    url = 'http://{}/status/{}'.format(BASE_URL, status_code)
    async with ClientSession(loop=loop, trace_configs=[trace_config]) as session:
        async with session.post(url):
            pass

    subsegment = xray_recorder.current_segment().subsegments[0]
    assert subsegment.name == url
    assert subsegment.error

    http_meta = subsegment.http
    assert http_meta['request']['url'] == url
    assert http_meta['request']['method'] == 'POST'
    assert http_meta['response']['status'] == status_code


async def test_throttle(loop, recorder):
    xray_recorder.begin_segment('name')
    trace_config = aws_xray_trace_config()
    status_code = 429
    url = 'http://{}/status/{}'.format(BASE_URL, status_code)
    async with ClientSession(loop=loop, trace_configs=[trace_config]) as session:
        async with session.head(url):
            pass

    subsegment = xray_recorder.current_segment().subsegments[0]
    assert subsegment.name == url
    assert subsegment.error
    assert subsegment.throttle

    http_meta = subsegment.http
    assert http_meta['request']['url'] == url
    assert http_meta['request']['method'] == 'HEAD'
    assert http_meta['response']['status'] == status_code


async def test_fault(loop, recorder):
    xray_recorder.begin_segment('name')
    trace_config = aws_xray_trace_config()
    status_code = 500
    url = 'http://{}/status/{}'.format(BASE_URL, status_code)
    async with ClientSession(loop=loop, trace_configs=[trace_config]) as session:
        async with session.put(url):
            pass

    subsegment = xray_recorder.current_segment().subsegments[0]
    assert subsegment.name == url
    assert subsegment.fault

    http_meta = subsegment.http
    assert http_meta['request']['url'] == url
    assert http_meta['request']['method'] == 'PUT'
    assert http_meta['response']['status'] == status_code


async def test_invalid_url(loop, recorder):
    xray_recorder.begin_segment('name')
    trace_config = aws_xray_trace_config()
    async with ClientSession(loop=loop, trace_configs=[trace_config]) as session:
        try:
            async with session.get('http://doesnt.exist'):
                pass
        except Exception:
            # prevent uncatch exception from breaking test run
            pass

    subsegment = xray_recorder.current_segment().subsegments[0]
    assert subsegment.fault

    exception = subsegment.cause['exceptions'][0]
    assert exception.type == 'ClientConnectorError'
