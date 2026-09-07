# Federation project history and Archeon orientation

The 2026-09-07 revision uses 24 connected projects in 3094 and the separate, unconfirmed Archeon project. The original eight sites retain their Earth distances and previously fixed populations; intermediate 04's earlier inferred direction is reassigned away from the Archeon branch following the user's clarification. Six have completed human handover; Mirren and intermediate 04 are still handing over. All eight have reached open-surface habitability. Four subsequent projects have first residents, while twelve remain in ASI-led environmental engineering.

`data/federation-projects.json` is the editable project registry. `src/federation-history.cjs` attaches its history to the astronomy builder and supplies the project routes and display stages. Rebuild with `node src/build-space-data.cjs`. This uses current project data and does not require a historical review backup. The manuscript chronology in §3.12 must be updated alongside deliberate changes to these dates.

## Dates, sources and views

- `milestones` records achieved deployment, relay readiness, open surface, first residents, Phase 3 and completed handover dates. A null value is not an achieved event.
- `forecast` holds uncompleted targets; it must not be presented as a historical achievement.
- `sponsorNodeId` identifies the base from which a project's deployment was prepared. A base can relay craft long before its planetary ecology is ready. It does not have to reproduce every precision or curvature component locally.
- Archeon's initial deployment came from Earth in 2472. Its own relay became available in 2484; intermediate 02 acquired full relay capability in 2488 and served the subsequent old route. This avoids relying on that relay before it existed.
- The 2564 view hides the sixteen later project overlays, routes, search matches and visits. Real catalogue stars remain unchanged. The 3094 view shows the expanded branches. Future milestones and 3094 populations are not shown as 2564 facts.
- A project display state is a simultaneous story map, not an instantaneous message from that planet. Historical collapse, local first light and information carried by vessels remain distinct.

Fifteen new connecting legs lie within approximately 118–199 ly. Project 02 is a deliberate longer sideward deployment, about 276 ly from intermediate 02; it does not fill the missing 100–200 ly continuation toward Archeon. The outermost project remains about 594 ly from Earth. Intermediate 04 retains its 290 ly Earth distance but its previously inferred direction is moved to another branch. Intermediate 02 is now Archeon's nearest registered colonial neighbour, about 330 ly away. New project positions lie behind the outward plane through this last relay, making the Archeon branch visibly isolated. This layout expresses the history of project selection; it is not a physical hazard boundary, a permanent ban, or a claim that the forward direction contains no planets.

## Terraforming assumptions and limits

The registry distinguishes the oxygen already present from the net oxygen addition, rock and ocean sinks, local water processed, separated hydrogen, hydrogen export energy and a process power allowance. The working final atmosphere has approximately 100 kPa surface pressure and 21% oxygen by mole fraction. Nitrogen, water and partial abiotic oxygen are declared initial selection assumptions, not measured exoplanet properties.

Electrolysis and related processing use an assumed 25 MJ/kg of gross oxygen. Hydrogen is accounted separately at one eighth of the oxygen mass and is exported beyond the planetary gravity well with an assumed 50% lifting efficiency. It must not recombine with the surface oxygen. The allocated mean process power includes 35% headroom; other construction, climatic adjustments and warp propulsion have separate requirements. The resulting several-thousand-TW budgets differ strongly from Archeon's accepted 300–500 GW fixed ground infrastructure.

These are internally checked mass and energy budgets for fictional engineering. They do not establish a finished thermal design, globally stable climate, ecological succession, atmospheric escape rate, or real population of colonizable planets. Orbital collection, exported chemical energy, external radiators and surface heat require explicit treatment in any later detailed design. Matching an assumed stellar irradiation is only a screening check; no climate solver was run. The existing eight fictional planets' illustrative orbital radii now use comparable moderate irradiation; their fixed gravities and system locations are unchanged.

Primary research used to separate the screening questions:

- [Bryson et al., rocky habitable-zone occurrence](https://arxiv.org/abs/2010.14812): an HZ occurrence estimate is not a colonization-grade occurrence estimate.
- [Gunell et al., magnetic fields and atmospheric escape](https://www.aanda.org/component/article?access=doi&doi=10.1051%2F0004-6361%2F201832934): magnetic protection cannot be reduced to a universal on/off condition.
- [McKay and Marinova, making Mars habitable](https://journals.sagepub.com/doi/10.1089/153110701750137477): warming, oxygen accumulation and ecosystem development have different burdens and timescales. Its Mars assumptions are not a prediction of these fictional projects.

## Archeon: shared 60-degree rotation

All Archeon-system orbit vectors and spin bases use a shared quaternion, rotating the previous XY reference plane by −60 degrees about fixed J2000 X. This is the signed cartographic implementation of the requested 60-degree rotation. Archeon's obliquity remains 13 degrees; moon inclinations and all orbital radii and periods are unchanged. The Earth–Archeon–Betelgeuse locations remain fixed.

The nebula centre's resulting declination is about −29.319°. At Atheria, latitude +27.8°, upper culmination is about 32.881° above a level horizon. Frontier reaches about 34.681°, Skyleaf 28.681°, and Iris Hollow 38.681°. Terrain, daylight and weather still affect actual visibility. This is not a claim that the nebula is visible at every hour, or from every window.

The older north pole placed the nebula near the opposite celestial pole, about −89.3° declination. The common system rotation fixes the northern-continent visibility without rotating the stellar background or changing the planet's seasonal axial tilt. The manuscript's single double-moon conjunction sentence no longer places the nebula directly behind the moons, since the new ecliptic latitude still separates their centres.

Review, source backup, chronology checks, rendered-geometry checks and screenshots are retained under `review/federation-expansion-20260907` at the workspace root.

## Cruise speed and progressive branching

The 31st-century cruise working value is 500c. Earth–Archeon is approximately 1.06 years one way and 2.12 years round trip in flight. Intermediate 02–Archeon is approximately 0.66 years one way and 1.32 years round trip; the user's year-scale round trip refers to this relay leg. Stops, survey and contact operations are additional. The Axiom generation stays at 100c. Intermediate working generations are 200c around 2800, 300c around 2880, 400c around 2940, then 500c from about 3000. These are fictional engineering milestones.

Forward surveys fail to produce an approved near continuation, while other directions gradually yield deployable targets. Once their orbital bases are usable, later seed fleets depart from them and the network accumulates along those branches. No colony is required as a warp gate, and a missing commercial or settlement continuation does not itself excuse failing to send a dedicated surface-confirmation mission.
