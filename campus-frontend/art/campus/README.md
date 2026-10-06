# Campus architecture · Professor / X Lab / X Gate

Three locally authored Blender assets extend the Libpedia material and construction language. No remote generation service or third-party architectural model is used.

- **Professor:** four-level research building with inset glazing, structural floor edges, bronze sunshades, roof balustrades, meeting furniture and a ground-floor discussion desk.
- **X Lab:** segmented observatory dome with skylight and standing seams, clerestory, service louvres, a maker bench and modeled printer components.
- **X Gate:** ceramic-clad portal piers, panel joints, fasteners, metal caps, slatted soffit, recessed lights and extruded wayfinding lettering.

Open **建筑细节** in the campus view switcher, then choose a building. Exterior, front, side and interior presets inspect the actual runtime assets. Switching inspection targets does not change the player's position. The navigation button walks from the player's current position to the selected building.

## Source and rebuild

`professor.blend`, `lab.blend`, `gate.blend` retain named, editable parts and bevel modifiers. `build_campus.py` deterministically recreates them, bakes short-range vertex ambient occlusion, batches geometry by material and exports the three GLBs under `public/assets/`. See `asset-report.json` for sizes, triangle counts and placements.

```sh
blender --background --python art/campus/build_campus.py
npm test
npm run build
```

The local build used Blender 4.5.9, installed at ignored `.local/tools/Blender.app`.

## Runtime and verification

- Each building loads independently; failure leaves that building's procedural fallback visible.
- Ground walls and desks preserve existing collision envelopes. Main entrances stay level and unobstructed. Upper floors and rooftop details are architectural scenery; they are not a new multi-floor navigation system.
- Glass has transparent thin surfaces; physically modeled frames, shadow gaps, edge bevels and baked contact shading provide depth. One additional light per new hall is used, without shadow maps.
- Tests parse the actual GLBs, check finite geometry and mesh budgets, ray-test entrance clearance, verify partial-load fallback and inspect camera selection without teleporting the player.
- Browser QA covers the three exteriors, lab interior, building picker and day/night views. Distant city buildings and plaza landscaping remain the existing background assets.
