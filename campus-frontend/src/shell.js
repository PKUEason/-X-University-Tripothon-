import {buildingStudies} from './building-studies.js';
import {paintIdentity} from './identity.js';
export function createCampusShell({ document, session, getWorld, onNavigate, onProjects, onStudent, onSettings, onAgent, onTasks, toast }) {
  const $ = (s) => document.querySelector(s);
  let mode = "home", night = false;
  const history = ["home"];
  let cursor = 0;
  const stage = { created: "提出目标", clarifying: "澄清目标", quest_ready: "准备出发", library: "收集资料", professor: "与导师研讨", lab: "制定方案", project_ready: "行动计划已生成" };
  const destinations = [["gate", "X Gate", "从一个问题开始", "01"], ["library", "Libpedia", "连接知识与灵感", "02"], ["office", "Professor", "让问题更进一步", "03"], ["lab", "X Lab", "把灵感变成计划", "04"], ["plaza", "Plaza", "你的探索路线", "05"]];
  function setView(next, record = true) {
    if (record && next !== history[cursor]) {
      history.splice(cursor + 1);
      history.push(next);
      cursor = history.length - 1;
    }
    mode = next;
    document.body.dataset.view = next;
    $("#dashboard").hidden = next !== "home";
    $("#radial-menu").hidden = true;
    document.body.dataset.navigation="false";
    getWorld()?.setNavigationOpen?.(false);
    $("#radial-toggle").setAttribute("aria-expanded", "false");
    getWorld()?.setView(next);
    document.querySelectorAll("[data-view-mode]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.viewMode === next)));
    $("#view-name").textContent = { home: "大世界主页", overview: "校园总览", third: "第三人称", first: "第一人称", library: "校园建筑细节" }[next];
    $("#nav-back").disabled = cursor === 0;
    $("#nav-forward").disabled = cursor === history.length - 1;
    $("#rail-home").classList.toggle("rail-active", next === "home");
    render();
  }
  function navigate(id) {
    setView("third");
    onNavigate(id);
  }
  $("#nav-home").onclick = () => setView("home");
  $("#nav-back").onclick = () => {
    if (cursor > 0) setView(history[--cursor], false);
  };
  $("#nav-forward").onclick = () => {
    if (cursor < history.length - 1) setView(history[++cursor], false);
  };
  $("#brand-home").onclick = (e) => {
    e.preventDefault();
    setView("home");
  };
  $("#rail-home").onclick = () => setView("home");
  $("#rail-projects").onclick = onProjects;
  $("#rail-student").onclick = onStudent;
  $("#rail-agent").onclick = onAgent;
  $("#rail-settings").onclick = onSettings;
  $("#explore-world").onclick = () => setView("third");
  $("#resume-exploring").onclick = () => setView("third");
  $("#dashboard-new").onclick = () => {
    onProjects();
    $("#project-name").focus();
  };
  $("#dashboard-projects").onclick = onProjects;
  $("#dashboard-profile").onclick = onStudent;
  $("#dashboard-next").onclick = onAgent;
  $("#dashboard-tasks").onclick = onTasks;
  for (const b of document.querySelectorAll("[data-view-mode]")) b.onclick = () => setView(b.dataset.viewMode);
  for (const b of document.querySelectorAll('[data-library-preset]')) b.onclick = () => {
    getWorld()?.setInspectionPreset?.(b.dataset.libraryPreset);
    document.querySelectorAll('[data-library-preset]').forEach(p => p.setAttribute('aria-pressed',String(p===b)));
  };
  $('#building-study').onchange = () => {
    const id=$('#building-study').value,study=buildingStudies[id];
    getWorld()?.setInspectionBuilding?.(id);
    $('#study-title').textContent=study.title+'.';$('#study-description').textContent=study.description;
    $('[data-library-preset="inside"]').textContent=study.room;
    $('#library-enter').textContent=study.enter+' ↗';
    document.querySelectorAll('[data-library-preset]').forEach(p=>p.setAttribute('aria-pressed',String(p.dataset.libraryPreset==='hero')));
  };
  $('#library-enter').onclick = () => navigate($('#building-study').value);
  $("#night-toggle").onclick = () => {
    night = !night;
    getWorld()?.setNight(night);
    $("#night-toggle").textContent = night ? "☀ 日间" : "☾ 夜间";
    $("#night-toggle").setAttribute("aria-pressed", String(night));
    document.body.dataset.night = String(night);
  };
  function radial() {
    if(mode==="home"||mode==="library")return;
    const open = $("#radial-menu").hidden;
    if(open&&mode!=="third")setView("third");
    $("#radial-menu").hidden = !open;
    $("#radial-toggle").setAttribute("aria-expanded", String(open));
    document.body.dataset.navigation=String(open);
    getWorld()?.setNavigationOpen?.(open);
    if(open){getWorld()?.releaseCursor?.();getWorld()?.stop();$("#radial-close").focus();}else getWorld()?.captureCursor?.();
  }
  $("#radial-toggle").onclick = radial;
  $("#radial-close").onclick=radial;
  document.addEventListener("keydown", (e) => {
    if (document.querySelector("dialog[open]") || e.target.closest("input,textarea,select")) return;
    if (mode === "overview" && ["KeyW", "KeyA", "KeyS", "KeyD", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.code)) setView("third");
    if (e.code === "KeyM" && !e.repeat) {
      e.preventDefault();
      radial();
    }
    if (e.code === "Escape" && !$("#radial-menu").hidden) radial();
  });
  for (const [id, name, desc, num] of destinations) {
    const b = document.createElement("button");
    b.className = "destination";
    b.dataset.destination = id;
    b.innerHTML = `<span class="destination-number">${num}</span><span><strong>${name}</strong><small>${desc}</small></span><span class="destination-arrow">↗</span>`;
    b.onclick = () => navigate(id);
    $("#destinations").append(b);
    const r = document.createElement("button");
    r.className = "radial-item";
    r.dataset.destination=id;
    r.dataset.space=id;
    r.dataset.sector=num;
    r.setAttribute('aria-label',`${name} · ${desc} · 标记路线`);
    r.style.setProperty('--region-fill',`url(#atlas-glass-${id})`);
    const contour=Array.from({length:9},(_,i)=>`<path d="M${-50+i*4} ${145+i*12} Q${40+i*5} ${30+i*9} 135 ${90+i*9} T${330+i*4} ${90+i*10}"/>`).join('');
    r.innerHTML = `<svg class="region-terrain" viewBox="0 0 300 230" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="atlas-glass-${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#d9f6ff" stop-opacity=".4"/><stop offset=".5" stop-color="#7296d7" stop-opacity=".35"/><stop offset="1" stop-color="#c6acf2" stop-opacity=".4"/></linearGradient></defs><path class="region-depth" d="M25 30 L222 8 L293 60 L278 188 L83 223 L6 166 Z"/><path class="region-surface" d="M25 20 L222 0 L293 50 L278 178 L83 213 L6 156 Z"/><path class="region-highlight" d="M25 20 L222 0 L293 50 L278 178 L83 213 L6 156 Z"/><g class="region-contours">${contour}</g></svg><span class="region-label"><small>SECTOR ${num}</small><strong>${name}</strong><span class="nav-description">${desc}</span></span><span class="region-pin" aria-hidden="true"><i></i></span><span class="region-action" aria-hidden="true">标记路线 ↗</span>`;
    r.onclick = () => navigate(id);
    $("#radial-items").append(r);
  }
  function render() {
    const s = session.state, p = session.profile;
    const identity=paintIdentity(document.body,p?.role);
    $('#passport-role').textContent=identity.label;
    $('#passport-role-en').textContent=identity.english;
    $('#passport-logo').src='./assets/'+identity.logo;
    $('#student-button').title=(p?.nickname||'校园成员')+' · '+identity.label;
    $('#student-button').setAttribute('aria-label','校园身份：'+identity.label);
    $("#welcome-name").textContent = p?.nickname ? `${p.nickname}，欢迎回来` : "欢迎来到你的未来校园";
    $("#passport-name").textContent = p?.nickname || "新同学";
    $("#dashboard-project-title").textContent = s.title || s.goal || "带着一个问题，走进来。";
    $("#dashboard-stage").textContent = stage[s.quest.status] || "开始探索";
    $("#dashboard-goal").textContent = s.goal || "想学什么、研究什么，或者做出什么？与 Scholar 聊聊，让一个想法成为你的下一个项目。";
    $("#project-count").textContent = String(session.projects.length).padStart(2, "0");
    $("#dash-mode").textContent = session.mode?.mock_mode ? "演示 Agent" : s.fallbacks?.length ? "含降级示例" : session.mode ? "Agent 已连接" : "正在连接";
    $("#dashboard-status").textContent = stage[s.quest.status] || "开始探索";
    const list = $("#recent-projects");
    list.replaceChildren();
    session.projects.slice(0, 3).forEach((p2) => {
      const b = document.createElement("button");
      b.className = "recent-project";
      const name = document.createElement("strong");
      name.textContent = p2.title || p2.goal || "新项目";
      const small = document.createElement("small");
      small.textContent = stage[p2.quest.status] || "提出目标";
      b.append(name, small);
      b.onclick = onProjects;
      list.append(b);
    });
    if (!session.projects.length) {
      const p2 = document.createElement("p");
      p2.textContent = "你的第一个项目，从好奇心开始。";
      list.append(p2);
    }
  }
  setView("home");
  return { setView, render, get mode() {
    return mode;
  } };
}
