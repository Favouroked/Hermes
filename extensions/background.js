const API_BASE_URL = 'http://localhost:8080';
let googleState = {active:false,urls:[],index:0,runId:null,installationId:null,links:[]};
const manualTasks = new Map();
const LINKS_KEY = 'linksRun';

async function saveLinks(state){await chrome.storage.local.set({[LINKS_KEY]:state});}
async function loadLinks(){const value=await chrome.storage.local.get(LINKS_KEY);return value[LINKS_KEY]||{active:false,links:[],index:0,currentTabId:null,installationId:null};}
async function post(path,body){const response=await fetch(API_BASE_URL+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!response.ok)throw new Error(await response.text());return response.json();}

chrome.runtime.onMessage.addListener((request,sender,sendResponse)=>{
  if(request.action==='startGoogleSearch') startGoogleSearch(request).catch(console.error);
  if(request.action==='googleLinks') googleLinks(request.links||[],sender.tab&&sender.tab.id,request.done);
  if(request.action==='captchaDetected') chrome.notifications.create({type:'basic',iconUrl:'icon48.png',title:'Hermes captcha',message:'Solve the captcha in the open tab to continue.'});
  if(request.action==='startLinks') startLinks(request.links,request.installationId).catch(console.error);
  if(request.action==='terminateLinks') terminateLinks().catch(console.error);
  if(request.action==='getCurrentLink') loadLinks().then(s=>sendResponse({link:s.links[s.index]||null}));
  if(request.action==='openAndExecute') chrome.tabs.create({url:request.url,active:true}).then(tab=>manualTasks.set(tab.id,request.actions||[]));
  return true;
});

async function startGoogleSearch(request){googleState={active:true,urls:request.urls,index:0,runId:request.search_run_id,installationId:request.installationId,links:[]};await chrome.storage.local.set({googleState,currentRoute:'results'});await openGoogle();}
async function openGoogle(){if(!googleState.active||googleState.index>=googleState.urls.length){googleState.active=false;chrome.runtime.sendMessage({action:'googleComplete'});return;}chrome.runtime.sendMessage({action:'googleProgress',current:googleState.index+1,total:googleState.urls.length});const tab=await chrome.tabs.create({url:googleState.urls[googleState.index],active:true});googleState.tabId=tab.id;}
async function googleLinks(links,tabId,done){if(!googleState.active||tabId!==googleState.tabId)return;googleState.links=[...new Set([...googleState.links,...links])];await chrome.storage.local.set({googleState});chrome.runtime.sendMessage({action:'googleLinks',links});if(!done)return;try{await chrome.tabs.remove(tabId);}catch(e){}googleState.index++;await openGoogle();}

async function startLinks(links,installationId){await saveLinks({active:true,links,index:0,currentTabId:null,installationId});await openNextLink();}
async function openNextLink(){const state=await loadLinks();if(!state.active||state.index>=state.links.length){state.active=false;await saveLinks(state);chrome.runtime.sendMessage({action:'linksComplete'});return;}const tab=await chrome.tabs.create({url:state.links[state.index].url,active:true});state.currentTabId=tab.id;await saveLinks(state);chrome.runtime.sendMessage({action:'linkProgress',current:state.index+1,total:state.links.length,link:state.links[state.index]});}
async function terminateLinks(){const state=await loadLinks();state.active=false;await saveLinks(state);chrome.runtime.sendMessage({action:'linksTerminated'});}
async function markProcessed(state,item){await fetch(`${API_BASE_URL}/api/automaton/links/${item.id}/processed`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({installation_id:state.installationId,notes:item.notes||''})});}

chrome.tabs.onRemoved.addListener(async tabId=>{const state=await loadLinks();if(!state.active||state.currentTabId!==tabId)return;const item=state.links[state.index];try{await markProcessed(state,item);}catch(e){console.error(e);}state.index++;state.currentTabId=null;await saveLinks(state);setTimeout(openNextLink,300);});

async function pageHtml(tabId){try{const result=await chrome.tabs.sendMessage(tabId,{action:'getPageHtml'});return result||'';}catch(e){return '';}}
chrome.tabs.onUpdated.addListener(async(tabId,changeInfo,tab)=>{if(changeInfo.status!=='complete')return;const state=await loadLinks();if(state.active&&state.currentTabId===tabId){try{const actions=await post('/api/auto-fill/check',{installation_id:state.installationId,url:tab.url,html:await pageHtml(tabId)});if(actions.length)chrome.tabs.sendMessage(tabId,{action:'executeActions',actions});}catch(e){console.error('link auto-fill',e);}}});

chrome.tabs.onUpdated.addListener(async(tabId,changeInfo,tab)=>{
  if(changeInfo.status!=='complete'||!tab.url||/^chrome:|^chrome-extension:/.test(tab.url))return;
  const state=await loadLinks();if(state.active&&state.currentTabId===tabId)return;
  const stored=await chrome.storage.local.get('installationId');if(!stored.installationId)return;
  try{const settings=await fetch(`${API_BASE_URL}/api/settings?installation_id=${encodeURIComponent(stored.installationId)}`).then(r=>r.json());if(!settings.auto_fill)return;const actions=await post('/api/auto-fill/check',{installation_id:stored.installationId,url:tab.url,html:await pageHtml(tabId)});if(actions.length)chrome.tabs.sendMessage(tabId,{action:'executeActions',actions});}catch(e){console.debug('Hermes auto-fill unavailable',e);}
});

chrome.tabs.onUpdated.addListener(async(tabId,changeInfo)=>{
  if(changeInfo.status!=='complete'||!manualTasks.has(tabId))return;
  const actions=manualTasks.get(tabId);manualTasks.delete(tabId);
  if(actions.length)chrome.tabs.sendMessage(tabId,{action:'executeActions',actions});
});
