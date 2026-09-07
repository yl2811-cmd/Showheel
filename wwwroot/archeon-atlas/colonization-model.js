/* Federation research model. All distances are physical three-dimensional ly.
 * The factory is deliberately self-contained so file:// pages can run it in a Blob Worker.
 * No DOM, network, clock, renderer, or canon mutation is used by the kernel. */
(function (root, factory) {
  'use strict';
  var api = factory();
  api.createKernel = factory;
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ATLAS_COLONIZATION = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function createKernel() {
  'use strict';
  var VERSION = '1.0.0', EPS = 1e-8, BLOCK = 500, YEAR_SECONDS = 365.25 * 86400, stateIndexes = new WeakMap();
  var defaults = { seed: 240024, densityFactor: 1, populationTrend: 'declining', intentFactor: 1, terraformFactor: 1 };
  var curve = [[2564, .20], [2664, .15], [2764, .09], [2864, .05], [2964, .02], [3094, .01]];
  function copy(x) { return JSON.parse(JSON.stringify(x)); }
  function compare(a, b) { return a < b ? -1 : a > b ? 1 : 0; }
  function distance(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
  function lerp(a, b, f) { return a.map(function (x, i) { return x + (b[i] - x) * f; }); }
  function warpSpeedAt(year) { return year >= 3000 ? 500 : year >= 2940 ? 400 : year >= 2880 ? 300 : year >= 2800 ? 200 : 100; }
  function physicalFractionAt(year, trend) {
    var value = curve[0][1];
    if (year >= curve[curve.length - 1][0]) value = curve[curve.length - 1][1];
    else for (var i = 1; i < curve.length; i++) if (year <= curve[i][0]) {
      var a = curve[i - 1], b = curve[i];
      value = a[1] + (b[1] - a[1]) * Math.max(0, (year - a[0]) / (b[0] - a[0])); break;
    }
    return trend === 'constant' ? .20 : trend === 'slower' ? .20 - (.20 - value) * .5 : value;
  }
  function demandRate(year, config) { return .1 * (.2 + .8 * physicalFractionAt(year, config.populationTrend) / .20) * config.intentFactor; }
  function demandBetween(start, end, config) {
    config = Object.assign({}, defaults, config);
    start = Math.max(2564, start); if (end <= start) return 0;
    var cuts = [start].concat(curve.map(function (p) { return p[0]; }).filter(function (y) { return y > start && y < end; }), [end]);
    var sum = 0; for (var i = 1; i < cuts.length; i++) sum += (cuts[i] - cuts[i - 1]) * (demandRate(cuts[i], config) + demandRate(cuts[i - 1], config)) / 2;
    return sum;
  }
  function hash(text) { var h = 2166136261; for (var i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function rng(seed) { var x = seed >>> 0; return function () { x += 0x6D2B79F5; var t = Math.imul(x ^ x >>> 15, 1 | x); t ^= t + Math.imul(t ^ t >>> 7, 61 | t); return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function sampleBlock(seed, bx, by, bz, densityFactor, templates) {
    densityFactor = densityFactor == null ? 1 : densityFactor;
    if (!(densityFactor > 0 && densityFactor <= 4)) throw new Error('densityFactor must be greater than zero and at most four.');
    var random = rng(hash(seed + ':' + bx + ':' + by + ':' + bz)), lambda = 4e-7 * BLOCK * BLOCK * BLOCK;
    var limit = Math.exp(-lambda), product = 1, n = 0;
    do { n++; product *= Math.max(Number.MIN_VALUE, random()); } while (product > limit);
    var result = [];
    for (var i = 0; i < n - 1; i++) {
      var position = [(bx + random()) * BLOCK, (by + random()) * BLOCK, (bz + random()) * BLOCK];
      var keep = random(), templateIndex = Math.floor(random() * (templates ? templates.length : 8));
      if (keep < densityFactor / 4) result.push({ id: 'candidate:' + bx + ':' + by + ':' + bz + ':' + i, name: '研究候选 ' + bx + '·' + by + '·' + bz + ' / ' + (i + 1), positionLy: position, templateId: templates ? templates[templateIndex].id : templateIndex, sourceCategory: 'hypothesis', block: [bx, by, bz] });
    }
    return result;
  }
  function normalize(options) {
    var c = Object.assign({}, defaults, options || {});
    c.seed = Number(c.seed);
    if (!Number.isSafeInteger(c.seed)) throw new Error('seed must be a safe integer.');
    [['densityFactor', [.25, 1, 4]], ['intentFactor', [.5, 1, 2]], ['terraformFactor', [.7, 1, 1.3]]].forEach(function (entry) { c[entry[0]] = Number(c[entry[0]]); if (entry[1].indexOf(c[entry[0]]) < 0) throw new Error('Unsupported ' + entry[0]); });
    if (['declining', 'slower', 'constant'].indexOf(c.populationTrend) < 0) throw new Error('Unsupported populationTrend');
    return c;
  }
  function Heap() { this.items = []; }
  Heap.prototype.push = function (item) { var q = this.items, i = q.length; q.push(item); while (i) { var p = (i - 1) >> 1; if (q[p].year <= item.year) break; q[i] = q[p]; i = p; } q[i] = item; };
  Heap.prototype.peek = function () { return this.items.length ? this.items[0].year : Infinity; };
  Heap.prototype.pop = function () { var q = this.items, top = q[0], last = q.pop(); if (q.length) { var i = 0; while (true) { var l = i * 2 + 1, r = l + 1; if (l >= q.length) break; var child = r < q.length && q[r].year < q[l].year ? r : l; if (q[child].year >= last.year) break; q[i] = q[child]; i = child; } q[i] = last; } return top; };
  function stageAt(p, year) {
    var m = p.milestones;
    if (p.isHome) return 'home';
    if (p.id === 'archeon' && year >= p.closedYear) return 'local-civilization';
    if (m.handoverYear != null && year >= m.handoverYear) return 'autonomous';
    if (m.phase3Year != null && year >= m.phase3Year) return 'handover';
    if (m.firstResidentsYear != null && year >= m.firstResidentsYear) return 'residents';
    if (m.surfaceReadyYear != null && year >= m.surfaceReadyYear) return 'surface';
    return year >= m.relayReadyYear ? 'base' : 'deployment';
  }
  function scaledEngineering(template, factor) {
    var e = copy(template.engineering), duration = template.terraformYears * factor;
    e.templateProjectYears = template.terraformYears; e.projectYears = duration;
    e.meanProcessPowerTW = e.totalProcessEnergyJ / (duration * YEAR_SECONDS * 1e12);
    e.allocatedMeanPowerTW = e.meanProcessPowerTW * 1.35;
    e.availableProcessEnergyJ = e.allocatedMeanPowerTW * 1e12 * duration * YEAR_SECONDS;
    e.terraformFactor = factor; e.budgetSufficient = e.availableProcessEnergyJ >= e.totalProcessEnergyJ && e.waterProcessedKg <= e.localWaterInventoryKg;
    return e;
  }
  function simulate(input, options) {
    var config = normalize(options), startYear = input.startYear || 2400, freeStart = input.freeStartYear || 2564, endYear = input.endYear || 3094;
    if (!input.anchors || !input.templates || input.templates.length !== 8) throw new Error('Eight immutable templates and fixed anchors are required.');
    var projects = copy(input.anchors), candidates = [], tasks = [], routes = [], events = [], heap = new Heap();
    var byId = new Map(), templates = new Map(input.templates.map(function (t) { return [t.id, t]; })), blocks = new Map(), bases = new Map();
    var confirmed = [], nextProject = 1, taskCounter = 0, credit = 0, lastYear = freeStart;
    var archeon = projects.find(function (p) { return p.id === 'archeon'; }), excludedRadius = 330;
    if (!archeon) throw new Error('Archeon anchor is required.');
    projects.forEach(function (p) { p.anchor = true; byId.set(p.id, p); bases.set(p.id, { project: p, surveyFree: Math.max(freeStart, p.milestones.relayReadyYear), seedFree: Math.max(freeStart, p.seedReadyYear), noSurveyUntil: 0 }); });
    function alive(p, year) { return p.closedYear == null || year < p.closedYear - EPS; }
    function queue(year, kind, data) { if (Number.isFinite(year)) heap.push({ year: year, kind: kind, data: data }); }
    function event(year, kind, fields) { events.push(Object.assign({ year: year, kind: kind }, fields)); }
    function addTask(fields) { var t = Object.assign({ id: 'task-' + (++taskCounter) }, fields); tasks.push(t); return t; }
    function milestones(p) {
      Object.keys(p.milestones).forEach(function (kind) { var y = p.milestones[kind]; if (y != null) event(y, kind, { projectId: p.id, historical: !!p.anchor }); });
      event(p.seedReadyYear, 'seed-ready', { projectId: p.id, historical: !!p.anchor });
    }
    projects.forEach(function (p) {
      milestones(p);
      if (p.isHome) return;
      var from = byId.get(p.sponsorNodeId), d = distance(from.positionLy, p.positionLy), leg = p.deploymentLeg;
      var dep = leg ? leg.departureYear : p.milestones.deploymentYear - 1 - d / 100;
      var arrival = dep + d / 100, deploy = p.milestones.deploymentYear;
      if (arrival > deploy + EPS) throw new Error('Fixed deployment predates actual arrival: ' + p.id);
      var task = addTask({ kind: 'seed', historical: true, fromId: from.id, toId: p.id, fromPositionLy: from.positionLy, toPositionLy: p.positionLy, departureYear: dep, arrivalYear: arrival, returnDepartureYear: deploy, returnYear: deploy + d / 100, speedC: 100, distanceLy: d, deploymentYear: deploy, historicalHandlingYears: deploy - arrival });
      routes.push({ id: 'history-' + p.id, kind: 'history', fromId: from.id, toId: p.id, fromPositionLy: from.positionLy, toPositionLy: p.positionLy, distanceLy: d, openedYear: deploy, tripCount: 1, taskIds: [task.id], historical: true });
      event(dep, 'departure', { taskId: task.id, projectId: p.id }); event(arrival, 'arrival', { taskId: task.id, projectId: p.id });
    });
    function getBlock(bx, by, bz, year) {
      var key = bx + ',' + by + ',' + bz;
      if (!blocks.has(key)) {
        var list = sampleBlock(config.seed, bx, by, bz, config.densityFactor, input.templates);
        list.forEach(function (c) { c.firstSeenYear = year; c.storyExcluded = distance(c.positionLy, archeon.positionLy) < excludedRadius - EPS; candidates.push(c); });
        blocks.set(key, list);
      }
      return blocks.get(key);
    }
    function minBlockDistance(pos, bx, by, bz) {
      var coords = [bx, by, bz], sum = 0;
      for (var i = 0; i < 3; i++) { var lo = coords[i] * BLOCK, hi = lo + BLOCK, v = pos[i] < lo ? lo - pos[i] : pos[i] > hi ? pos[i] - hi : 0; sum += v * v; }
      return Math.sqrt(sum);
    }
    function nearestCandidate(base, year) {
      var pos = base.project.positionLy, maxDistance = warpSpeedAt(year) * 5, b = pos.map(function (x) { return Math.floor(x / BLOCK); });
      var best = null, bestDistance = maxDistance + EPS, maxShell = Math.ceil(maxDistance / BLOCK) + 1;
      // Lazy shells do not impose a volume boundary; unvisited blocks have an exact geometric lower bound.
      for (var shell = 0; shell <= maxShell; shell++) {
        for (var bx = b[0] - shell; bx <= b[0] + shell; bx++) for (var by = b[1] - shell; by <= b[1] + shell; by++) for (var bz = b[2] - shell; bz <= b[2] + shell; bz++) {
          if (Math.max(Math.abs(bx - b[0]), Math.abs(by - b[1]), Math.abs(bz - b[2])) !== shell || minBlockDistance(pos, bx, by, bz) > bestDistance) continue;
          var block = getBlock(bx, by, bz, year);
          for (var j = 0; j < block.length; j++) { var c = block[j]; if (c.surveyTaskId) continue; var d = distance(pos, c.positionLy); if (d <= maxDistance + EPS && (d < bestDistance - EPS || Math.abs(d - bestDistance) <= EPS && (!best || c.id < best.id))) { best = c; bestDistance = d; } }
        }
        var outer = Math.min.apply(null, pos.map(function (v, axis) { return Math.min(v - (b[axis] - shell) * BLOCK, (b[axis] + shell + 1) * BLOCK - v); }));
        if (outer > Math.min(bestDistance, maxDistance) + EPS) break;
      }
      return best;
    }
    function assignSurveys(year) {
      Array.from(bases.values()).sort(function (a, b) { return compare(a.project.id, b.project.id); }).forEach(function (base) {
        var p = base.project;
        if (!alive(p, year) || base.surveyFree > year + EPS || base.noSurveyUntil > year + EPS || p.milestones.relayReadyYear > year + EPS) return;
        var c = nearestCandidate(base, year);
        if (!c) { base.noSurveyUntil = year + 10; queue(year + 10, 'wake'); return; }
        var d = distance(p.positionLy, c.positionLy), speed = warpSpeedAt(year), arrive = year + d / speed, backDep = arrive + 3, back = backDep + d / speed;
        var task = addTask({ kind: 'survey', fromId: p.id, toId: c.id, fromPositionLy: p.positionLy, toPositionLy: c.positionLy, departureYear: year, arrivalYear: arrive, returnDepartureYear: backDep, returnYear: back, validationYear: back + 10, speedC: speed, distanceLy: d });
        if (p.closedYear != null && task.validationYear >= p.closedYear) task.closedYear = p.closedYear;
        c.surveyTaskId = task.id; c.surveyDepartureYear = year; c.surveyReturnYear = back; c.confirmationYear = task.validationYear; c.surveyFromId = p.id;
        if (task.closedYear != null) { c.surveyClosedYear = task.closedYear; c.confirmationYear = null; }
        base.surveyFree = back;
        queue(back, 'wake'); if (c.confirmationYear != null) queue(c.confirmationYear, 'confirmed', c);
        event(year, 'survey-departure', { taskId: task.id, candidateId: c.id, fromId: p.id });
        if (task.closedYear == null || arrive < task.closedYear) event(arrive, 'survey-arrival', { taskId: task.id, candidateId: c.id });
        if (task.closedYear == null || back < task.closedYear) event(back, 'survey-return', { taskId: task.id, candidateId: c.id });
        if (task.closedYear != null) event(task.closedYear, 'survey-ended', { taskId: task.id, candidateId: c.id, reason: 'Fixed cessation of Archeon external activity; unfinished investigation is not counted as confirmed.' });
        if (c.confirmationYear != null) event(c.confirmationYear, 'candidate-confirmed', { candidateId: c.id, storyExcluded: c.storyExcluded });
        routes.push({ id: 'survey-' + task.id, kind: 'survey', fromId: p.id, toId: c.id, fromPositionLy: p.positionLy, toPositionLy: c.positionLy, distanceLy: d, openedYear: year, closedYear: task.closedYear == null ? back : Math.min(back, task.closedYear), taskIds: [task.id], tripCount: 1 });
      });
    }
    function dispatch(year) {
      while (credit >= 1 - EPS) {
        var free = Array.from(bases.values()).filter(function (b) { return b.seedFree <= year + EPS && b.project.seedReadyYear <= year + EPS && alive(b.project, year + 8); });
        if (!free.length) return;
        var best = null;
        for (var i = 0; i < confirmed.length; i++) {
          var c = confirmed[i]; if (c.projectId || c.storyExcluded) continue;
          var template = templates.get(c.templateId);
          for (var j = 0; j < free.length; j++) {
            var b = free[j], p = b.project, d = distance(p.positionLy, c.positionLy), departure = year + 8, speed = warpSpeedAt(departure);
            var deployment = departure + d / speed + 1, surface = deployment + template.terraformYears * config.terraformFactor;
            if (!best || surface < best.surface - EPS || Math.abs(surface - best.surface) <= EPS && (d < best.distance - EPS || Math.abs(d - best.distance) <= EPS && c.id + '/' + p.id < best.candidate.id + '/' + best.base.project.id)) best = { candidate: c, base: b, distance: d, departure: departure, speed: speed, deployment: deployment, surface: surface, template: template };
          }
        }
        if (!best) return;
        var candidate = best.candidate, source = best.base.project, tmpl = best.template;
        var id = 'research-' + String(nextProject++).padStart(4, '0');
        var relay = best.deployment + tmpl.relayLagYears, surfaceYear = best.surface;
        var project = { id: id, name: '研究项目 ' + id.slice(9), positionLy: candidate.positionLy.slice(), anchor: false, sourceCategory: 'hypothesis', sponsorNodeId: source.id, candidateId: candidate.id, templateId: tmpl.id,
          milestones: { deploymentYear: best.deployment, relayReadyYear: relay, surfaceReadyYear: surfaceYear, firstResidentsYear: surfaceYear + 3, phase3Year: surfaceYear + 11, handoverYear: surfaceYear + 101 },
          seedReadyYear: relay + 15, population3094: null, approvalYear: year, engineering: scaledEngineering(tmpl, config.terraformFactor),
          selectionReason: '在已完成调查、有完整意愿份额及可用船队的组合中，预计最早取得开放地表；相同结果按三维航程与稳定编号排序。',
          selection: { confirmedYear: candidate.confirmationYear, demandCreditBefore: credit, sourceSlotFreeYear: best.base.seedFree, predictedSurfaceYear: surfaceYear, distanceLy: best.distance, templateId: tmpl.id },
          deploymentLeg: { distanceLy: best.distance, speedC: best.speed, departureYear: best.departure, handlingAllowanceYears: 1 } };
        var task = addTask({ kind: 'seed', fromId: source.id, toId: id, candidateId: candidate.id, fromPositionLy: source.positionLy, toPositionLy: project.positionLy, assemblyStartYear: year, departureYear: best.departure, arrivalYear: best.departure + best.distance / best.speed, returnDepartureYear: best.deployment, returnYear: best.deployment + best.distance / best.speed, speedC: best.speed, distanceLy: best.distance, deploymentYear: best.deployment });
        candidate.projectId = id; candidate.selectedYear = year; project.seedTaskId = task.id;
        credit = Math.max(0, credit - 1); best.base.seedFree = task.returnYear;
        projects.push(project); byId.set(id, project); bases.set(id, { project: project, surveyFree: relay, seedFree: project.seedReadyYear, noSurveyUntil: 0 });
        queue(relay, 'wake'); queue(project.seedReadyYear, 'wake'); queue(task.returnYear, 'wake');
        milestones(project); event(year, 'project-approved', { projectId: id, candidateId: candidate.id, demandSpent: 1, demandCreditAfter: credit });
        event(best.departure, 'departure', { taskId: task.id, projectId: id }); event(task.arrivalYear, 'arrival', { taskId: task.id, projectId: id }); event(task.returnYear, 'seed-slot-free', { taskId: task.id, projectId: source.id });
        routes.push({ id: 'history-' + id, kind: 'history', fromId: source.id, toId: id, fromPositionLy: source.positionLy, toPositionLy: project.positionLy, distanceLy: best.distance, openedYear: best.deployment, taskIds: [task.id], tripCount: 1 });
      }
    }
    queue(freeStart, 'wake'); [2800, 2880, 2940, 3000, endYear].forEach(function (year) { queue(year, 'technology'); });
    event(2573, 'external-activity-ends', { projectId: 'archeon', localCivilizationContinues: true }); queue(2573, 'wake');
    projects.forEach(function (p) { if (p.milestones.relayReadyYear > freeStart) queue(p.milestones.relayReadyYear, 'wake'); if (p.seedReadyYear > freeStart) queue(p.seedReadyYear, 'wake'); });
    while (heap.peek() <= endYear + EPS) {
      var next = heap.peek();
      if (credit < 1 - EPS && demandBetween(lastYear, next, config) + credit >= 1 - EPS) {
        var lo = lastYear, hi = next;
        for (var iteration = 0; iteration < 48; iteration++) { var mid = (lo + hi) / 2; if (credit + demandBetween(lastYear, mid, config) >= 1) hi = mid; else lo = mid; }
        next = hi;
      }
      credit += demandBetween(lastYear, next, config); lastYear = next;
      while (heap.peek() <= next + EPS) { var item = heap.pop(); if (item.kind === 'confirmed') confirmed.push(item.data); }
      assignSurveys(next); dispatch(next);
    }
    addServicesAndCrosslinks(projects, byId, routes, tasks, events, startYear, endYear, addTask);
    events.sort(function (a, b) { return a.year - b.year || compare(a.kind, b.kind) || compare(String(a.projectId || a.taskId || a.candidateId), String(b.projectId || b.taskId || b.candidateId)); });
    var result = { version: VERSION, config: config, startYear: startYear, freeStartYear: freeStart, endYear: endYear, inputSources: copy(input.sources || {}), assumptions: copy(input.assumptions || []), projects: projects, candidates: candidates, tasks: tasks, routes: routes, events: events,
      diagnostics: { generatedBlockCount: blocks.size, generatedCandidateCount: candidates.length, storyExcludedCount: candidates.filter(function (c) { return c.storyExcluded; }).length, approvedProjects: nextProject - 1, demandAccrued: demandBetween(freeStart, endYear, config), demandCredit: Math.max(0, demandBetween(freeStart, endYear, config) - (nextProject - 1)), fixedHistoryProjectCount: projects.filter(function (p) { return p.anchor && !p.isHome; }).length, isolationRadiusLy: excludedRadius, blockSizeLy: BLOCK, candidateDensityPerLy3: 1e-7 * config.densityFactor, minTemplateYears: Math.min.apply(null, input.templates.map(function (t) { return t.terraformYears; })), maxTemplateYears: Math.max.apply(null, input.templates.map(function (t) { return t.terraformYears; })), maxSurveyDistanceLy: 2500, finiteUniverseBoundary: false } };
    return result;
  }
  function addServicesAndCrosslinks(projects, byId, routes, tasks, events, startYear, endYear, addTask) {
    var regular = [], initiated = new Set();
    function closed(a, b) { var c = Math.min(a.closedYear == null ? Infinity : a.closedYear, b.closedYear == null ? Infinity : b.closedYear); return Number.isFinite(c) ? c : null; }
    function route(a, b, year, kind) {
      var stop = closed(a, b), r = { id: kind + '-' + a.id + '-' + b.id, kind: kind, fromId: a.id, toId: b.id, fromPositionLy: a.positionLy, toPositionLy: b.positionLy, distanceLy: distance(a.positionLy, b.positionLy), openedYear: year, closedYear: stop, tripCount: 0, taskIds: [], vesselCount: 1 };
      if (stop != null && stop <= year) return null;
      regular.push(r); routes.push(r); events.push({ year: year, kind: kind + '-opened', routeId: r.id }); return r;
    }
    projects.filter(function (p) { return !p.isHome; }).forEach(function (p) { var a = byId.get(p.serviceNodeId || p.sponsorNodeId); route(a, p, Math.max(p.milestones.relayReadyYear, a.milestones.relayReadyYear), 'service'); });
    function pathDistance(from, to, year) {
      var distances = new Map([[from, 0]]), seen = new Set();
      while (true) { var best = null, bestD = Infinity; distances.forEach(function (d, id) { if (!seen.has(id) && d < bestD) { bestD = d; best = id; } }); if (best == null) return Infinity; if (best === to) return bestD; seen.add(best);
        regular.forEach(function (r) { if (r.openedYear > year + EPS || r.closedYear != null && r.closedYear <= year + EPS) return; var other = r.fromId === best ? r.toId : r.toId === best ? r.fromId : null; if (other && bestD + r.distanceLy < (distances.has(other) ? distances.get(other) : Infinity)) distances.set(other, bestD + r.distanceLy); });
      }
    }
    var dates = Array.from(new Set([startYear].concat(projects.map(function (p) { return p.milestones.handoverYear; }).filter(function (y) { return y != null && y <= endYear; }), regular.map(function (r) { return r.openedYear; }).filter(function (y) { return y <= endYear; })))).sort(function (a, b) { return a - b; });
    dates.forEach(function (year) {
      var mature = projects.filter(function (p) { return p.milestones.handoverYear != null && p.milestones.handoverYear <= year + EPS && (p.closedYear == null || p.closedYear > year); }).sort(function (a, b) { return compare(a.id, b.id); });
      mature.forEach(function (a) { if (initiated.has(a.id)) return;
        var eligible = mature.filter(function (b) { return b.id !== a.id && !regular.some(function (r) { return r.openedYear <= year + EPS && (r.closedYear == null || r.closedYear > year) && (r.fromId === a.id && r.toId === b.id || r.toId === a.id && r.fromId === b.id); }); }).sort(function (b, c) { return distance(a.positionLy, b.positionLy) - distance(a.positionLy, c.positionLy) || compare(b.id, c.id); });
        if (!eligible.length) return; var b = eligible[0], old = pathDistance(a.id, b.id, year), direct = distance(a.positionLy, b.positionLy);
        if (direct <= old * .75 + EPS) { var r = route(a, b, year, 'crosslink'); if (r) { r.initiatedBy = a.id; r.priorNetworkDistanceLy = Number.isFinite(old) ? old : null; r.savingFraction = Number.isFinite(old) ? 1 - direct / old : 1; initiated.add(a.id); } }
      });
    });
    regular.forEach(function (r) {
      var a = byId.get(r.fromId), b = byId.get(r.toId), departure = Math.max(startYear, r.openedYear);
      while (departure <= endYear + EPS && (r.closedYear == null || departure < r.closedYear - EPS)) {
        var speed = warpSpeedAt(departure), travel = r.distanceLy / speed;
        var inhabited = b.milestones.firstResidentsYear != null && departure >= b.milestones.firstResidentsYear;
        var task = addTask({ kind: 'service', routeId: r.id, routeKind: r.kind, fromId: a.id, toId: b.id, fromPositionLy: a.positionLy, toPositionLy: b.positionLy, departureYear: departure, arrivalYear: departure + travel, returnDepartureYear: departure + travel + 1, returnYear: departure + 2 * travel + 1, speedC: speed, distanceLy: r.distanceLy, closedYear: r.closedYear });
        r.taskIds.push(task.id); r.tripCount++;
        departure += Math.max(2 * travel + 1, inhabited ? 2 : 5);
      }
    });
  }
  function stateAt(result, requestedYear) {
    var year = Math.max(result.startYear, Math.min(result.endYear, Number(requestedYear)));
    if (!Number.isFinite(year)) throw new Error('Playback year must be finite.');
    var visible = result.projects.filter(function (p) { return p.milestones.deploymentYear <= year + EPS; });
    var indexes = stateIndexes.get(result);
    if (!indexes) { indexes = { taskById: new Map(result.tasks.map(function (t) { return [t.id, t]; })), seedTasks: result.tasks.filter(function (t) { return t.kind === 'seed'; }) }; stateIndexes.set(result, indexes); }
    var projectIds = new Set(visible.map(function (p) { return p.id; })), taskById = indexes.taskById;
    var busySources = new Set(indexes.seedTasks.filter(function (t) { return !t.historical && t.assemblyStartYear <= year + EPS && t.returnYear > year + EPS; }).map(function (t) { return t.fromId; }));
    var names = { home: '母星', deployment: '设施展开', base: '基地可用', surface: '开放地表', residents: '先期住民', handover: '交接中', autonomous: '自治', 'local-civilization': '本地文明延续' };
    var projects = visible.map(function (p) {
      var stage = stageAt(p, year), relay = year >= p.milestones.relayReadyYear && (p.closedYear == null || year < p.closedYear);
      var milestoneState = {}; Object.keys(p.milestones).forEach(function (key) { milestoneState[key] = p.milestones[key] != null && p.milestones[key] <= year + EPS ? p.milestones[key] : null; });
      var activeSeed = busySources.has(p.id);
      // Future dates belong to an explicitly labelled forecast, not completed milestones.
      return Object.assign({}, p, { milestones: milestoneState, forecastMilestones: copy(p.milestones), status: names[stage], stage: stage, population: Math.abs(year - 3094) < EPS ? p.population3094 : null, population3094: Math.abs(year - 3094) < EPS ? p.population3094 : null, relayOperational: relay, canSeed: relay && year >= p.seedReadyYear && !activeSeed, seedSlotBusy: activeSeed, seedReadyYear: year >= p.seedReadyYear ? p.seedReadyYear : null, forecastSeedReadyYear: p.seedReadyYear, surfaceHabitable: p.milestones.surfaceReadyYear != null && year >= p.milestones.surfaceReadyYear });
    });
    var candidates = result.candidates.filter(function (c) { return c.firstSeenYear <= year + EPS && !projectIds.has(c.projectId); }).map(function (c) {
      var departure = c.surveyDepartureYear != null && c.surveyDepartureYear <= year + EPS, returned = c.surveyReturnYear != null && c.surveyReturnYear <= year + EPS;
      var confirmed = c.confirmationYear != null && c.confirmationYear <= year + EPS, selected = c.selectedYear != null && c.selectedYear <= year + EPS, ended = c.surveyClosedYear != null && c.surveyClosedYear <= year + EPS;
      var stage = ended ? 'survey-ended' : selected ? 'approved' : confirmed ? c.storyExcluded ? 'story-excluded' : 'confirmed' : returned ? 'validation' : departure ? 'survey' : 'candidate';
      return { id: c.id, name: c.name, positionLy: c.positionLy, sourceCategory: 'hypothesis', templateId: confirmed ? c.templateId : null, firstSeenYear: c.firstSeenYear, storyExcluded: c.storyExcluded, stage: stage, status: { 'survey-ended': '调查终止', approved: '已批准，尚未部署', 'story-excluded': '已调查 · 故事约束未批准', confirmed: '工程验证完成', validation: '材料验证中', survey: '无人调查中', candidate: '模型候选' }[stage], surveyTaskId: departure ? c.surveyTaskId : null, confirmationYear: confirmed ? c.confirmationYear : null, selectedYear: selected ? c.selectedYear : null, projectId: selected ? c.projectId : null };
    });
    var ships = [];
    result.tasks.forEach(function (t) {
      if (t.departureYear > year + EPS || t.returnYear <= year + EPS || t.closedYear != null && t.closedYear <= year + EPS) return;
      var phase, pos;
      if (year < t.arrivalYear) { phase = 'outbound'; pos = lerp(t.fromPositionLy, t.toPositionLy, (year - t.departureYear) / (t.arrivalYear - t.departureYear)); }
      else if (year < t.returnDepartureYear) { phase = t.kind === 'survey' ? 'onsite' : t.kind === 'seed' ? 'unloading' : 'turnaround'; pos = t.toPositionLy.slice(); }
      else { phase = 'return'; pos = lerp(t.toPositionLy, t.fromPositionLy, (year - t.returnDepartureYear) / (t.returnYear - t.returnDepartureYear)); }
      ships.push(Object.assign({}, t, { id: 'ship-' + t.id, taskId: t.id, phase: phase, positionLy: pos }));
    });
    var activeSeedTasks = indexes.seedTasks.filter(function (t) { return t.departureYear <= year + EPS && t.returnYear > year + EPS && (t.closedYear == null || t.closedYear > year); });
    var routes = result.routes.filter(function (r) { return r.openedYear <= year + EPS && (r.kind === 'history' || r.closedYear == null || r.closedYear > year + EPS); }).map(function (r) {
      var departures = (r.taskIds || []).map(function (id) { return taskById.get(id); }).filter(function (t) { return t && t.departureYear <= year + EPS; });
      var recent = departures.filter(function (t) { return t.departureYear > year - 20; }).length;
      return Object.assign({}, r, { taskIds: departures.map(function (t) { return t.id; }), tripCount: departures.length, departuresLast20Years: recent, frequencyPerYear: recent / 20, active: r.closedYear == null || r.closedYear > year, closedYear: r.closedYear != null && r.closedYear <= year + EPS ? r.closedYear : null });
    });
    activeSeedTasks.forEach(function (t) { routes.push({ id: 'seed-' + t.id, kind: 'seed', fromId: t.fromId, toId: t.toId, fromPositionLy: t.fromPositionLy, toPositionLy: t.toPositionLy, distanceLy: t.distanceLy, openedYear: t.departureYear, taskIds: [t.id], tripCount: 1, speedC: t.speedC, departureYear: t.departureYear, arrivalYear: t.arrivalYear, returnYear: t.returnYear }); });
    var colonies = projects.filter(function (p) { return !p.isHome; }), approvals = result.events.filter(function (e) { return e.kind === 'project-approved' && e.year <= year + EPS; }).length;
    return { year: year, projects: projects, candidates: candidates, ships: ships, routes: routes, stats: {
      projectCount: colonies.length, openSurfaceCount: colonies.filter(function (p) { return p.surfaceHabitable; }).length,
      residentCount: colonies.filter(function (p) { return p.milestones.firstResidentsYear != null; }).length,
      activeShipCount: ships.length, extentLy: Math.max.apply(null, [0].concat(colonies.map(function (p) { return Math.hypot.apply(null, p.positionLy); }))),
      physicalFraction: physicalFractionAt(year, result.config.populationTrend), demandCredit: Math.max(0, demandBetween(result.freeStartYear, year, result.config) - approvals),
      regularRouteCount: routes.filter(function (r) { return r.kind === 'service' || r.kind === 'crosslink'; }).length,
      approvedProjectCount: approvals, candidateCount: candidates.length, warpSpeedC: warpSpeedAt(year)
    } };
  }
  return { version: VERSION, defaults: defaults, simulate: simulate, stateAt: stateAt, warpSpeedAt: warpSpeedAt, physicalFractionAt: physicalFractionAt, demandBetween: demandBetween, sampleBlock: sampleBlock, distance: distance };
});
