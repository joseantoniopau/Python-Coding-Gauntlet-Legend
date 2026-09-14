import assert from 'node:assert/strict';
import {formatProse} from '../../web/js/markup.js';
assert.equal(formatProse("`'** hi **'`"), "<code>'** hi **'</code>", 'Python string contents are literal');
assert.equal(formatProse('```python\nprint("**hi**")\n```'), '<pre>print("**hi**")\n</pre>');
assert.equal(formatProse('`a < b` & **check**'), '<code>a &lt; b</code> &amp; <b style="color:var(--gold-hi)">check</b>');
assert.equal(formatProse('<script>alert(1)</script>'), '&lt;script&gt;alert(1)&lt;/script&gt;');
console.log('Prose: Python operators and strings remain literal; HTML escaped.');
