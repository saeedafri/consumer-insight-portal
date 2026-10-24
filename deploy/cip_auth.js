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

function check(r) {
    if (!r.variables.cookie_cip_session && /^Bearer cip_/.test(r.headersIn.Authorization || '')) {
        return r.return(403);   // an API key (app/core/api_keys.py): the API checks it
    }
    const raw = (r.variables.cookie_cip_session || '').replace(/^"|"$/g, '');   // the API may set it quoted
    const dot = raw.lastIndexOf('.');
    if (!SECRET || dot < 1) {
        return r.return(401);
    }
    const value = Buffer.from(raw.slice(0, dot), 'base64url').toString();
    const expected = crypto.createHmac('sha256', SECRET).update(value).digest('base64url');
    const parts = value.split('|');
    if (!same(raw.slice(dot + 1), expected) || parts.length !== 5
            || Number(parts[2]) < Date.now() / 1000 || revoked(parts[3])) {
        return r.return(401);
    }
    return r.return(parts[4] === '*' ? 204 : 403);
}

export default { check };
