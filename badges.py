import os
import json
import time
from flask import Flask, render_template, Response, request
import requests
from redis import StrictRedis


app = Flask(__name__)
app.debug = os.environ.get('DEBUG') == '1'
app.config['REDIS_URL'] = os.environ.get('REDISTOGO_URL') or 'redis://localhost/5'


redis = StrictRedis.from_url(app.config['REDIS_URL'])
VALIDATION_URL = 'https://wasipaid.com/receipt'


@app.route('/callback', methods=['POST'])
def ripple_event():
    """This url will be called by wasipaid.com when a configured event occurs;
    in this case: when the WCG giveaway address makes a payment.
    """

    # First, make sure this is a valid request by posting back to wasipaid.com
    # Be sure to post back the exact data received, before decoding the JSON
    # (which would likely reorder keys etc).
    result = requests.post(VALIDATION_URL, data=request.data)
    if result.text != 'VALID':
        # Apparently not; ignore it. Should the real service have a bug, let it redeliver.
        return 'not at all ok', 400

    data = json.loads(request.data)['data']
    # Ignore any non-XRP payments
    if data['currency'] == 'XRP':
        user = data['destination']

        # Store what the user received and when
        redis.hmset('address:{}'.format(user), {
            'amount': data['amount'],
            'when': time.time()
        })

    # Return an OK string so we won't receive this notification again
    return 'OK', 200


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/sample')
def sample():
    # Generate a sample badge
    badge = make_svg_badge('12345', True)
    return Response(badge, content_type='image/svg+xml')


@app.route('/<ripple>')
def badge(ripple):
    # Get this user's info
    data = redis.hgetall('address:{}'.format(ripple))
    if not data:
        amount = 0
        powered = False
    else:
        amount = data['amount']
        powered = (time.time() - float(data['when'])) < 3600*24

    badge = make_svg_badge(amount, powered)
    return Response(badge, content_type='image/svg+xml')


def make_svg_badge(xrp_count, powered=True):
    # I hate SVG now.
    badge_template =  \
u"""<?xml version="1.0" encoding="UTF-8"?>
<svg version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xml:space="preserve" preserveAspectRatio="none" width="118" height="25" viewBox="0 0 227 48">
<filter id="grayscale">
  <feColorMatrix type="matrix" values="0.3333 0.3333 0.3333 0 0 0.3333 0.3333 0.3333 0 0 0.3333 0.3333 0.3333 0 0 0 0 0 1 0"/>
 </filter>
<g  filter="{filter}">
<g id="Left1">
    <rect id="LeftBG" x="1" y="1" fill="#557FC0" stroke="#557FC0" stroke-width="2" stroke-miterlimit="10" width="75" height="46"/>
    <g id="WCG">
        <path fill="#FFFFFF" d="M12.762,37.783L7.112,8.216h3.479l2.477,14.258c0.609,3.729,1.088,7.02,1.436,10.66h0.174
            c0.348-3.729,1.043-6.932,1.74-10.704L19.11,8.216h2.869l2.695,13.907c0.652,3.509,1.305,6.887,1.695,11.011h0.131
            c0.479-4.255,1-7.458,1.564-10.836l2.436-14.082h3.26l-5.695,29.567h-3.26l-2.826-14.389c-0.564-3.115-1.131-6.449-1.479-9.694
            h-0.086c-0.436,3.334-0.914,6.535-1.609,9.826l-2.912,14.257H12.762L12.762,37.783z"/>
        <path fill="#FFFFFF" d="M49.759,37.258c-0.914,0.481-2.348,0.789-4.174,0.789c-5.738,0-9.824-4.649-9.824-14.696
            c0-11.669,5.738-15.397,10.346-15.397c1.783,0,3.043,0.351,3.652,0.745l-0.74,2.852c-0.695-0.307-1.434-0.614-2.957-0.614
            c-3.129,0-6.779,3.071-6.779,12.107c0,9.037,3.303,12.021,6.867,12.021c1.262,0,2.391-0.307,3.086-0.658L49.759,37.258z"/>
        <path fill="#FFFFFF" d="M66.885,37.037c-1.26,0.526-3.346,1.01-5.215,1.01c-2.566,0-4.957-0.701-6.912-2.896
            c-2.131-2.28-3.566-6.36-3.521-11.757C51.28,11.9,57.106,7.953,62.278,7.953c1.826,0,3.262,0.351,4.174,0.833l-0.738,2.896
            c-0.783-0.395-1.826-0.702-3.391-0.702c-3.652,0-7.609,2.939-7.609,12.108c0,9.125,3.436,12.063,6.957,12.063
            c1.129,0,1.781-0.219,2.043-0.351v-9.651H59.93v-2.808h6.957v14.695H66.885z"/>
    </g>
</g>
<g id="Right">
    <rect id="RightBG" x="76" y="1" fill="#FFFFFF" stroke="#557FC0" stroke-width="2" stroke-miterlimit="10" width="150" height="46"/>
    <text id="Amount" {non_ie} y="32" width="50" height="46" fill="#557FC0" stroke="#557FC0"  stroke-width="2" font-family="'Segoe UI', 'Bitstream Vera Sans', 'DejaVu Sans', 'Bitstream Vera Sans', 'Trebuchet MS', Verdana, 'Verdana Ref', sans-serif" font-size="25">{text}</text>
</g>
</g>
</svg>
"""
    ie_compat = 'MSIE' in request.headers.get('User-Agent')

    text = u'{:.0f} XRP'.format(float(xrp_count))
    if ie_compat:
        # IE does not support the textLength attribute for stretching a
        # text when combined with text-anchor="end".
        non_ie_code = 'textLength="135" x="85" text-anchor="start"'
        pads = 0
    else:
        non_ie_code = 'textLength="135" x="218" text-anchor="end"'

    # If the text is long, we let SVG stretch it. That looks bad if its too short, so pad
    # with a space that will not be removed.
    if len(text) < 7:
        pads = 2
    elif len(text) < 1:
        pads = 1
    else:
        pads = 0

    text = u'\u3000'*pads  + text
    badge = badge_template.format(
        text=text,
        filter='url(#grayscale)' if not powered else '',
        non_ie=non_ie_code)
    return badge


if __name__ == '__main__':
    app.run()

