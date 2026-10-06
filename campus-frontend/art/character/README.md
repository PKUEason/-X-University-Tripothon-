# Designer explorer · rig and animation

The supplied static Tripo FBX is now bound to a locally authored 17-bone armature with up to four normalized skin influences per vertex. The GLB includes the original surface artwork and three authored, looping, in-place clips: Idle (3 s), Walk (20/30 s), Run (16/30 s). These are newly created motions, not recovered Tripo motion data.

## Source and rebuild

- `explorer-rigged.blend`: editable mesh, packed textures, weights, armature and actions.
- `build_character.py`: deterministic binding and animation source.
- `../../public/assets/student-rigged.glb`: runtime asset, 3,953,528 bytes.
- `asset-report.json`: exported inventory.

Run from campus-frontend:

```sh
.local/tools/Blender.app/Contents/MacOS/Blender --background --python art/character/build_character.py -- /absolute/path/to/source.fbx
npm test
npm run build
```

The source FBX remains in ignored `.local/designer-character`; the Blender file has packed textures. No paid generation service is used.

## Integration

`createStudent` retains the original procedural model during loading or on failure, and replaces it only after successful validation. Cloned armatures and animation mixers are independent for the campus and profile preview. Shared geometry and textures are retained when switching profiles.

Actual movement selects Walk, Shift movement selects Run, and stopping selects Idle with a 0.18 s crossfade. Cadence follows actual distance travelled; nominal gait speeds are 1.2 m/s for Walk and 2.025 m/s for Run. Reduced motion allows the stop transition to finish before freezing idle breathing.

Role colors are visible on the arm and chest accents; the designer texture is preserved. The provided asset is one character appearance: existing gender metadata is retained, but this mesh does not have separate male/female variants. No fingers, face, cloth or accessory physics are independently animated.

## Verification · 2026-10-06

- 68 frontend tests passed and production build passed.
- Actual GLB tests cover embedded textures, 17 joints, normalized weights, looping animations, independent clones, Idle/Walk/Run transitions, finite deformed vertices, loading fallback, distance-based cadence and reduced-motion stopping.
- Re-rendered the latest Blender source for Idle, three Walk samples and Run; reviewed updated side walking and frontal running poses. Earlier pre-fix images must not be used to assess the current binding.
- Browser confirmed the designer texture/model, auto-walking to Plaza, arrival panel and return to Idle. Diagnostics report `designer-rigged`, `ready`, `Idle`, and zero application errors. Full held-key sprint in-browser was not separately captured; Run is verified by the actual GLB animation tests and rendered pose.
- GLB was already identical in the deployment snapshot. This turn's cadence/transition/diagnostic updates are copied to the local deployment checkout but not pushed or redeployed.


## Side-view gait revision · 2026-10-06

User review found crouched support legs and a rigid head. The previous fixed -5 cm walking hip offset is replaced with support-dependent height: the body rises over the supporting leg and lowers at weight transfer. Added heel strike / toe-off, swing clearance, coordinated opposite-arm swing, torso counter-rotation and delayed head motion. Run keeps its existing timing; corrected shoe binding applies to all clips.

Shoe weights now follow each connected shoe surface, including vertices crossing the body centre line; the previous x-sign split pulled inner sole vertices toward the opposite foot. The original artwork is retained.

Side-view review uses ten evenly spaced poses over a complete cycle, with an animated before/after comparison at `.local/gait-review/walk-side-comparison.gif`. Actual GLB regression checks verify >160-degree supporting-knee extension at midstance, changing head height/orientation, and no shoe triangle bound rigidly to both feet. All 69 frontend tests and the production build pass. Naturalness remains a visual judgement; these checks guard the specific crouching and sole-stretching defects.

The updated GLB and regression tests are copied to the local deployment checkout. No remote push or Render redeploy was performed.


## Continuous gait revision · 2026-10-06

- Matched horizontal foot velocity and acceleration across stance/swing boundaries; lift now has zero endpoint velocity.
- Replaced abrupt support-leg minimum and resetting loading dip with smooth, periodic blending. Applied a circular five-sample pose filter to the complete Walk pose, including the cycle seam.
- Baked at 60 Hz (Idle 180, Walk 40, Run 32 frames), preserving each clip duration and world walking speed. At the fixed 160-sample diagnostic, peak discrete hip acceleration falls from 366.7 to 97.6; this is a regression metric, not a claim of biological gait accuracy.
- Route movement consumes remaining per-frame distance across waypoints instead of snapping ahead and introducing a stopped frame. Regression verifies continuous motion and no position jumps through Lab's approach route.
- 71 tests passed; production build and diff checks passed. Browser navigation to X Lab completed with no logged application errors.
- Same-rate 60 fps side-by-side review: `.local/gait-smooth/comparison-60fps.mp4` (previous / smooth). Earlier 15 fps GIF is not suitable for judging rendering smoothness.
- Updated GLB, runtime and tests are synced to the local deployment checkout only; no remote deployment performed.


## Per-foot sole calibration · 2026-10-06

User correctly identified that one foot stayed tipped up. The static source shoe meshes have different bind-pose sole slopes: about -1.2 degrees on L, +29.2 degrees on R. Previous equal-bone-angle checks did not detect this surface asymmetry.

Each shoe now derives its own pitch correction from the robust slope of its lower longitudinal envelope (L +1.19 degrees, R -29.29 degrees). The correction is included in ankle clearance and target foot orientation for Idle, Walk and Run. Standing now also solves both feet onto the ground. Existing torso rotation and smooth walking transitions remain.

Regression inspects the actual GLB skinned shoe vertices: both soles are within 3 degrees of level and 6 mm of ground in support/idle; both rise through toe-off in their own phase. Measured midpoint sole angles are about -0.04 and +0.83 degrees, replacing the former right-foot 29-degree tilt. Left and right side renders independently confirm ground contact. All 72 tests, build and diff checks passed.

60 fps close side comparison: `.local/foot-contact/comparison-60fps.mp4`. Updated GLB/test copied to local deployment checkout; not pushed or redeployed.


## Ankle deformation repair · 2026-10-06

The previous sole-angle fix leveled the floor contact but left a permanent rotation across a low ankle pivot and a horizontal weight cutoff. The calf/cuff could fold and surface edges stretched to 6.1x their bind length in Walk (9.2x in Run).

Neutralized the asymmetric shoe pitch in the bind mesh before heat binding, fading the correction through the cuff/calf. Designer topology, UVs and artwork are retained. Moved ankle/knee pivots to the cuff/leg, made complete shoe surfaces rigid with gradual sock and knee weights, and explicitly separated nearby finger components. Shortened stride to fit the leg and coordinated toe-off/early-swing pitch; runtime cadence uses the new 0.87 m/s Walk and 1.359375 m/s Run reference speeds while world movement speed is unchanged. Source previews now use the same linear skinning as glTF.

Actual GLB regression checks all three clips at 80 phases for shoe/ankle edge tearing or collapse, alongside existing sole contact, support-knee extension, loop and smoothing checks. 78 frontend tests and production build passed. Walk diagnostic peak edge stretch is 1.72x and its 99th percentile 1.13x; these are regression metrics, not a guarantee of human-motion realism. Both side views reviewed throughout the full cycle; browser reload reports no application errors.

Review: `.local/ankle-fix/comparison-60fps.mp4` shows LEFT SIDE / RIGHT SIDE of the current animation. GLB, cadence runtime and tests copied to the local deployment checkout only; no push or remote redeploy.


## Published release · 2026-10-06

The accepted character, motion runtime, smooth route stepping and prior rounded clipping fix are live at https://x-university-demo.onrender.com/ in deployment commit `e83a5553e340e0f8c6a69287ccbba945c439f979`. Isolated release tests: 73/73 passed. Four online asset/source hashes match the release. The unrelated pending feedback changes remain local. Deployment evidence lives in `x-university-deploy/.local/character-release-verification.json`.
