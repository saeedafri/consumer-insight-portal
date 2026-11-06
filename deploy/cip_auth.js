// The sign-in check nginx runs before every data file (deploy/nginx.conf, location /_auth): the same rule as
// app/core/session.read — an HMAC-SHA256 signed "email|products|expires|session id|scope" cookie that has not expired
// and was not revoked — so a burst of thousands of people never queues on the Python API just to prove who they are.
//   204  signed in, and sees every survey and feature (scope "*"): nginx may serve the shared published file
//   403  signed in, but filtered (a client, or a smaller tier): nginx hands the request to the API (error_page 403 = @api)
//   401  not signed in
import crypto from 'crypto';
import fs from 'fs';

const SECRET = process.env.CIP_SESSION_SECRET || '';
const REVOKED = process.env.CIP_REVOKED_FILE || '';   // hashes of revoked session ids, one per line, written by the API

function revoked(sid) {
    if (!REVOKED) {
        return false;
    }
    try {
        const hash = crypto.createHash('sha256').update(sid).digest('hex');
        return fs.readFileSync(REVOKED, 'utf8').indexOf(hash) !== -1;
    } catch (e) {
        return false;   // no file yet: nothing revoked
    }
}

// constant time: njs's crypto module has no timingSafeEqual, so compare every byte whatever differs first
function same(a, b) {
    if (a.length !== b.length) {
        return false;
    }
    let diff = 0;
    for (let i = 0; i < a.length; i++) {
        diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
    }
    return diff === 0;
}

function status(raw) {
    const dot = raw.lastIndexOf('.');
    if (!SECRET || dot < 1) {
        return 401;
    }
    const value = Buffer.from(raw.slice(0, dot), 'base64url').toString();
    const expected = crypto.createHmac('sha256', SECRET).update(value).digest('base64url');
    const parts = value.split('|');
    if (!same(raw.slice(dot + 1), expected) || parts.length !== 5
            || Number(parts[2]) < Date.now() / 1000 || revoked(parts[3])) {
        return 401;
    }
    return parts[4] === '*' ? 204 : 403;
}

// Each cookie's answer is remembered for 60 s (the "sessions" zone, deploy/nginx.conf): the check above with its
// file read cost ~90 % of a cached answer's time (5 Nov 2026: 10,000 → 90,000 answers/s). A revoked or expired
// session therefore works for up to 60 s more in nginx, the same as the API's own minute poll (api/signin.load_revoked).
function check(r) {
    if (!r.variables.cookie_cip_session && /^Bearer cip_/.test(r.headersIn.Authorization || '')) {
        return r.return(403);   // an API key (app/core/api_keys.py): the API checks it
    }
    const raw = (r.variables.cookie_cip_session || '').replace(/^"|"$/g, '');   // the API may set it quoted
    return r.return(remembered(raw));
}

// The cookie's answer from the 60 s memory, else checked now and remembered
function remembered(raw) {
    const known = ngx.shared.sessions.get(raw);
    if (known) {
        return Number(known);
    }
    const answer = status(raw);
    if (raw) {
        ngx.shared.sessions.set(raw, String(answer));
    }
    return answer;
}

// The signed-in email for the request log ($cip_user, deploy/cip_logs.conf), so the Logs page's "Top visitors" can
// name people instead of only addresses. Only a valid, signed cookie names anyone; the cookie itself is never logged
// (it would let whoever reads the logs sign in as that person).
function user(r) {
    const raw = (r.variables.cookie_cip_session || '').replace(/^"|"$/g, '');
    if (!raw || remembered(raw) === 401) {
        return '';
    }
    return Buffer.from(raw.slice(0, raw.lastIndexOf('.')), 'base64url').toString().split('|')[0];
}

export default { check, user };
