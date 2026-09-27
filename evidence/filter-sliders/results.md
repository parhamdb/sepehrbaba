# Filter discovery and live sliders

Scope: clearly labeled Filters tab, three immediately visible slider/number pairs,
visible minimum/maximum values, live per-section adjustments, and existing state
preservation. No filter-algorithm changes, retraining or source-data changes.

Fixed acceptance: four layouts (320×568, 390×844, 844×390, 1280×850), live touch
input/numeric sync/independent section settings, stable expanded slider ranges,
and unchanged server project. Budget: one discovery, focused failure checks,
one final run on committed source. Physical phones are not tested.

Discovery: standard phone/desktop layouts and live input passed. Narrow phone and
landscape clipped the final slider by 6–9 pixels; removing default range margins
and row gaps fixed both. Independent review caught expanded slider maxima
shrinking while dragging; per-section range retention fixes this behavior.

An earlier HTML interception test could not load the module because Chromium
classified the intercepted response and LAN module into different address spaces.
The staged check now serves the actual HTML and bundle from an isolated loopback
server. The deployed check uses the real LAN response without interception.

Final receipt and deployed artifact hashes will be recorded after source freeze.
