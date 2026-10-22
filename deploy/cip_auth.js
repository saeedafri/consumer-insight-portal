// The sign-in check nginx runs before every data file (deploy/nginx.conf, location /_auth): the same rule as
// api/main.user — an HMAC-SHA256 signed "email|products|expires" cookie that has not expired — so a burst of
// thousands of people never queues on the Python API just to prove who they are.
import crypto from 'crypto';

const SECRET = process.env.CIP_SESSION_SECRET || '';

function check(r) {
    const raw = (r.variables.cookie_cip_session || '').replace(/^"|"$/g, '');   // the API sets it quoted
    const dot = raw.lastIndexOf('.');
    if (!SECRET || dot < 1) {
        return r.return(401);
    }
    const value = Buffer.from(raw.slice(0, dot), 'base64url').toString();
    const expected = crypto.createHmac('sha256', SECRET).update(value).digest('base64url');
    const parts = value.split('|');
    if (expected !== raw.slice(dot + 1) || parts.length !== 3 || Number(parts[2]) < Date.now() / 1000) {
        return r.return(401);
    }
    return r.return(204);
}

export default { check };
