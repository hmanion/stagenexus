from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.config import settings


router = APIRouter(tags=["ui"])


def _nav_controls_html() -> str:
    return """
    <div class='app-nav-shell'>
      <div class='app-nav' id='appNav'>
        <button data-screen='home' onclick="navigateScreen('home')">Home</button>
        <button data-screen='my-work' onclick="navigateScreen('my-work')">My Work</button>
        <button data-screen='deals' onclick="navigateScreen('deals')">Scopes</button>
        <button data-screen='people' onclick="navigateScreen('people')">People</button>
        <button data-screen='campaigns' onclick="navigateScreen('campaigns')">Campaigns</button>
        <button data-screen='gantt' onclick="navigateScreen('gantt')">Gantt</button>
        <button data-screen='reviews' onclick="navigateScreen('reviews')">Reviews</button>
        <button data-screen='risks' onclick="navigateScreen('risks')">Risks</button>
        <button data-screen='capacity' onclick="navigateScreen('capacity')">Capacity</button>
        <button data-screen='admin' onclick="navigateScreen('admin')">Admin</button>
      </div>
      <div class='nav-controls-right'>
        <button type='button' class='ghost nav-refresh-btn' onclick='refreshAll()' aria-label='Refresh' title='Refresh'>&#x21bb;</button>
        <select id='roleMode' class='nav-user-select' onchange='refreshRoleMode()'></select>
      </div>
    </div>
"""


@router.get("/", response_class=HTMLResponse)
@router.get("/home", response_class=HTMLResponse)
@router.get("/my-work", response_class=HTMLResponse)
@router.get("/deals", response_class=HTMLResponse)
@router.get("/scopes", response_class=HTMLResponse)
@router.get("/people", response_class=HTMLResponse)
@router.get("/campaigns", response_class=HTMLResponse)
@router.get("/gantt", response_class=HTMLResponse)
@router.get("/reviews", response_class=HTMLResponse)
@router.get("/risks", response_class=HTMLResponse)
@router.get("/capacity", response_class=HTMLResponse)
@router.get("/admin", response_class=HTMLResponse)
def index() -> str:
    ui_flags = {
        "show_demo_rail": settings.show_demo_rail,
        "demo_rail_allowed_roles": list(settings.demo_rail_allowed_roles),
    }
    html = """<!doctype html>
<html lang='en'>
<head>
  <meta charset='UTF-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1.0' />
  <title>Today Digital Campaign Ops</title>
  <link rel='preload' href='/static/fonts/BarlowCondensed-800.ttf' as='font' type='font/ttf' crossorigin>
  <link rel='preload' href='/static/fonts/Epilogue-400.ttf' as='font' type='font/ttf' crossorigin>
  <link rel='preload' href='/static/fonts/DMMono-400.ttf' as='font' type='font/ttf' crossorigin>
  <link rel='stylesheet' href='/static/app.css' />
</head>
<body>
  <header>
    <h1>Today Digital Campaign Operations</h1>
__NAV_CONTROLS__
  </header>
  <div class='app-shell'>
    <button id='demoRailToggle' class='demo-rail-toggle hidden' onclick='toggleDemoRail()' aria-label='Show demo rail'>Show Demo Rail</button>
    <aside id='demoRail' class='demo-rail hidden' aria-label='Demo controls'>
      <section class='card demo-card'>
        <div class='section-head'>
          <h3>Demo Flow</h3>
          <span class='muted'>Left rail only</span>
        </div>
        <div class='actions'>
          <button data-control='create_demo_deal' onclick='createDemoDeal()'>Create Demo Scope</button>
          <button data-control='submit_latest_deal' onclick='submitLatestDeal()'>Submit Latest Scope</button>
          <button data-control='ops_approve_latest_deal' onclick='opsApproveLatestDeal()'>Ops Approve Scope + Readiness</button>
          <button data-control='generate_latest_campaigns' onclick='generateLatestDealCampaigns()'>Generate Campaigns</button>
        </div>
      </section>
      <section class='card demo-card'>
        <h3 style='margin-top:0;'>Workflow Demo</h3>
        <div class='actions'>
          <button data-control='complete_next_step' onclick='completeNextWorkflowStep()'>Complete Next Step</button>
          <button data-control='override_step_due' onclick='overrideNextWorkflowStepDue()'>Override Next Step Due</button>
          <button data-control='advance_deliverable' onclick='advanceFirstDeliverable()'>Advance Deliverable</button>
          <button data-control='run_ops_job' onclick='runOpsRiskCapacityJob()'>Run Ops Job</button>
          <button data-control='mark_ready_publish' onclick='markAnyReadyToPublish()'>Mark Ready To Publish</button>
        </div>
      </section>
      <section class='card demo-card'>
        <h3 style='margin-top:0;'>Demo Governance</h3>
        <div class='actions'>
          <button data-control='run_sow_change' onclick='createAndApproveSowChange()'>Run SOW Change</button>
          <button data-control='request_override' onclick='requestCapacityOverride()'>Request Capacity Override</button>
          <button data-control='approve_override' onclick='approveCapacityOverride()'>Approve Capacity Override</button>
          <button data-control='refresh_data' onclick='refreshAll()'>Refresh Data</button>
        </div>
      </section>
      <section class='card demo-card'>
        <div class='section-head'>
          <h3 style='margin:0;'>Demo Log</h3>
          <button id='demoRailMinimiseBtn' class='hidden' onclick='toggleDemoRail()'>Minimise</button>
        </div>
        <div class='log' id='log'>Ready.\n</div>
      </section>
    </aside>
    <main>
    <section class='card' id='sectionControls'>
      <div class='section-head'>
        <h3>Screen Options</h3>
        <span class='muted'>Quick filters</span>
      </div>
      <div class='toolbar'>
        <label class='sub' for='qCampaigns'>Campaigns</label>
        <select id='qCampaigns' aria-label='Filter campaigns' onchange='refreshAll()'>
          <option value='all'>All campaigns</option>
          <option value='not_started'>Not started</option>
          <option value='in_progress'>In Progress</option>
          <option value='on_hold'>On Hold</option>
          <option value='blocked_client'>Blocked: Client</option>
          <option value='blocked_internal'>Blocked: Internal</option>
          <option value='blocked_dependency'>Blocked: Dependency</option>
          <option value='done'>Done</option>
          <option value='cancelled'>Cancelled</option>
        </select>
        <label class='sub' for='qProducts'>Products</label>
        <select id='qProducts' aria-label='Filter products' onchange='refreshAll()'>
          <option value='all'>All products</option>
          <option value='demand'>Demand</option>
          <option value='amplify'>Amplify</option>
          <option value='response'>Response</option>
          <option value='display_only'>Display</option>
        </select>
        <label class='sub' for='qScopeHealth'>Scope health</label>
        <select id='qScopeHealth' aria-label='Filter scope health' onchange='refreshAll()'>
          <option value='all'>All scope health</option>
          <option value='on_track'>On Track</option>
          <option value='at_risk'>At Risk</option>
          <option value='off_track'>Off Track</option>
          <option value='not_started'>Not due</option>
        </select>
        <label class='sub' for='qCampaignHealth'>Campaign health</label>
        <select id='qCampaignHealth' aria-label='Filter campaign health' onchange='refreshAll()'>
          <option value='all'>All campaign health</option>
          <option value='on_track'>On Track</option>
          <option value='at_risk'>At Risk</option>
          <option value='off_track'>Off Track</option>
          <option value='not_started'>Not due</option>
        </select>
        <label class='sub' for='qUsersButton'>Users</label>
        <div id='qUsersDropdown' class='multi-filter-dropdown'>
          <button id='qUsersButton' type='button' class='ghost' aria-haspopup='true' aria-expanded='false' onclick='toggleUsersDropdown(event)'>All users</button>
          <div id='qUsersMenu' class='multi-filter-menu hidden' role='menu' aria-label='Filter by users'></div>
        </div>
        <select id='qUsers' aria-label='Filter by users' multiple class='hidden' onchange='refreshAll()'></select>
        <label class='sub' for='qUsersLogic'>Users logic</label>
        <select id='qUsersLogic' aria-label='User filter logic' onchange='refreshAll()'>
          <option value='or'>OR</option>
          <option value='and'>AND</option>
        </select>
      </div>
    </section>

    <section class='grid' id='kpis' aria-live='polite'></section>

    <section class='card hidden' id='sectionNotAllowed'>
      <h3>Not Available For This Role</h3>
      <p class='sub'>This screen is currently restricted for your selected role mode.</p>
    </section>

    <section class='card' id='sectionMyWork'>
      <div class='section-head'>
        <h3>My Work</h3>
        <span id='myWorkSummary' class='muted' aria-live='polite'></span>
      </div>
      <div class='toolbar' style='margin-bottom:8px;'>
        <label class='sub' for='myWorkMode'>Mode</label>
        <select id='myWorkMode' onchange='renderMyWork(currentRole, currentActorId)'>
          <option value='owned_only'>Owned only</option>
          <option value='owned_and_participant'>Owned + participant</option>
        </select>
      </div>
      <div class='queue-list' id='myWorkGrid'></div>
    </section>

    <section class='card' id='sectionActions'>
      <div class='section-head'>
        <h3>New Scope Intake</h3>
        <span class='muted'>Capture and submit commercial intake</span>
      </div>
      <details class='ops-accordion surface-2'>
        <summary>Scope Form</summary>
        <article>
          <p class='sub'>Capture commercial details and submit to Ops for triage.</p>
          <form id='dealForm' onsubmit='submitNewDeal(event)'>
            <div class='form-grid'>
              <div class='field'>
                <label for='dealClientName'>Client</label>
                <input id='dealClientName' required placeholder='Client name' />
              </div>
              <div class='field'>
                <label for='dealPublication'>Brand / Publication</label>
                <select id='dealPublication' required></select>
              </div>
              <div class='field full'>
                <label>Product Lines</label>
                <div class='line-list' id='productLines'></div>
                <div class='actions'>
                  <button type='button' onclick='addProductLine()'>Add Product Line</button>
                </div>
              </div>
              <div class='field'>
                <label for='dealSowStart'>SOW Start</label>
                <input id='dealSowStart' type='date' required onchange='recomputeDealEndDate()' />
              </div>
              <div class='field'>
                <label for='dealSowEnd'>SOW End</label>
                <input id='dealSowEnd' type='date' required />
              </div>
              <div class='field full'>
                <label for='dealICP'>ICP</label>
                <textarea id='dealICP' required placeholder='Ideal customer profile'></textarea>
              </div>
              <div class='field full'>
                <label for='dealObjective'>Campaign Objective</label>
                <textarea id='dealObjective' required placeholder='Primary objective'></textarea>
              </div>
              <div class='field full'>
                <label for='dealMessaging'>Messaging / Positioning</label>
                <textarea id='dealMessaging' required placeholder='Core narrative and positioning'></textarea>
              </div>
              <div class='field'>
                <label for='contactName'>Client Contact Name</label>
                <input id='contactName' placeholder='Primary contact' />
              </div>
              <div class='field'>
                <label for='contactEmail'>Client Contact Email</label>
                <input id='contactEmail' type='email' placeholder='contact@example.com' />
              </div>
              <div class='field full'>
                <label for='dealAttachment'>SOW Attachment (metadata for now)</label>
                <input id='dealAttachment' placeholder='SOW.pdf' />
              </div>
            </div>
            <div class='actions'>
              <button class='primary' data-control='create_deal' type='submit'>Create Scope</button>
              <button type='button' data-control='create_submit_deal' onclick='submitAndRouteLatestDeal()'>Create Scope + Submit to Ops</button>
            </div>
          </form>
        </article>
      </details>
    </section>

    <section class='card' id='sectionDeals'>
      <div class='section-head'>
        <h3>Scopes</h3>
        <span id='dealsCount' class='muted'></span>
      </div>
      <div id='dealsBody' class='queue-list'></div>
    </section>

    <section class='card' id='sectionPeople'>
      <div class='section-head'>
        <h3>People</h3>
        <span id='peopleCount' class='muted'></span>
      </div>
      <div class='toolbar'>
        <label class='sub' for='qPeopleTeam'>Team</label>
        <select id='qPeopleTeam' aria-label='Filter people by team' onchange='renderPeople()'>
          <option value='all'>All teams</option>
          <option value='sales'>Sales</option>
          <option value='editorial'>Editorial</option>
          <option value='marketing'>Marketing</option>
          <option value='client_services'>Client Services</option>
        </select>
        <label class='sub' for='qPeopleSeniority'>Seniority</label>
        <select id='qPeopleSeniority' aria-label='Filter people by seniority' onchange='renderPeople()'>
          <option value='all'>All seniority</option>
          <option value='standard'>Standard</option>
          <option value='manager'>Manager</option>
          <option value='leadership'>Leadership</option>
        </select>
        <label class='sub' for='qPeopleAppRole'>App Role</label>
        <select id='qPeopleAppRole' aria-label='Filter people by app role' onchange='renderPeople()'>
          <option value='all'>All app roles</option>
          <option value='user'>User</option>
          <option value='admin'>Admin</option>
          <option value='superadmin'>Superadmin</option>
        </select>
      </div>
      <div id='peopleBody' class='queue-list' style='margin-top:8px;'></div>
    </section>

    <section class='card' id='sectionCampaigns'>
      <div class='section-head'>
        <h3>Campaigns</h3>
        <span id='campaignsCount' class='muted'></span>
      </div>
      <div id='campaignsBody' class='queue-list'></div>
    </section>

    <section class='card' id='sectionGantt'>
      <div class='section-head'>
        <h3>Gantt</h3>
        <span id='ganttMeta' class='muted'>Select a campaign to view timeline</span>
      </div>
      <div class='toolbar'>
        <label class='sub' for='ganttCampaignSelect'>Campaign</label>
        <select id='ganttCampaignSelect' onchange='onGanttCampaignChange()'></select>
        <span class='sub'>Show</span>
        <div id='ganttKinds' class='gantt-kind-ticks'>
          <label><input type='checkbox' value='campaign' checked onchange='onGanttKindsChange()' /> Campaigns</label>
          <label><input type='checkbox' value='milestone' checked onchange='onGanttKindsChange()' /> Milestones</label>
          <label><input type='checkbox' value='stage' checked onchange='onGanttKindsChange()' /> Stages</label>
          <label><input type='checkbox' value='step' checked onchange='onGanttKindsChange()' /> Steps</label>
        </div>
        <button id='ganttMonthBtn' class='primary' onclick='setGanttView("month")'>Month</button>
        <button id='ganttWeekBtn' onclick='setGanttView("week")'>Week</button>
      </div>
      <div id='ganttBody' class='gantt-wrap' style='margin-top:10px;'>
        <div class='sub' style='padding:12px;'>No campaign selected.</div>
      </div>
    </section>

    <section class='card' id='sectionReviews'>
      <div class='section-head'>
        <h3>Reviews Queue</h3>
        <span id='reviewsSummary' class='muted'></span>
      </div>
      <table>
        <thead><tr><th>Queue</th><th>Step</th><th>Deliverable</th><th>Campaign</th><th>Due</th><th>Open</th></tr></thead>
        <tbody id='reviewsQueueBody'></tbody>
      </table>
    </section>

    <section class='card' id='sectionDeliverables'>
      <div class='section-head'>
        <h3>Deliverables</h3>
        <span id='deliverablesCount' class='muted'></span>
      </div>
      <div id='deliverablesBody' class='queue-list'></div>
    </section>

    <section class='card' id='sectionSteps'>
      <div class='section-head'>
        <h3>Workflow Steps</h3>
        <span id='stepsCount' class='muted'></span>
      </div>
      <table>
        <thead><tr><th>Name</th><th>Owner Role</th><th>Due</th><th>Done</th><th>ID</th></tr></thead>
        <tbody id='stepsBody'></tbody>
      </table>
    </section>

    <section class='card' id='sectionOpsDefaults'>
      <div class='section-head'>
        <h3>Ops Default Variables</h3>
        <span class='muted'>Head of Ops controls for workload (hours), capacity (hours/week), and turnaround times (days)</span>
      </div>
      <form id='opsDefaultsForm' onsubmit='saveOpsDefaults(event)'>
        <details class='ops-accordion surface-2'>
          <summary>Content Workload Defaults (hours)</summary>
          <div class='form-grid' style='padding:8px 10px;'>
            <div class='field'>
              <label for='opsWorkKoPrep'>KO/Planning Prep (hours)</label>
              <input id='opsWorkKoPrep' type='number' step='0.5' min='0' max='24' required />
            </div>
            <div class='field'>
              <label for='opsWorkContentPlan'>Content Plan Creation (hours)</label>
              <input id='opsWorkContentPlan' type='number' step='0.5' min='0' max='24' required />
            </div>
            <div class='field'>
              <label for='opsWorkInterview'>Interview Participation (hours)</label>
              <input id='opsWorkInterview' type='number' step='0.5' min='0' max='24' required />
            </div>
            <div class='field'>
              <label for='opsWorkArticle'>Article Drafting (hours)</label>
              <input id='opsWorkArticle' type='number' step='0.5' min='0' max='24' required />
            </div>
            <div class='field'>
              <label for='opsWorkVideoBrief'>Video Brief (hours)</label>
              <input id='opsWorkVideoBrief' type='number' step='0.5' min='0' max='24' required />
            </div>
            <div class='field'>
              <label for='opsWorkAmends'>Amends Reserve (hours)</label>
              <input id='opsWorkAmends' type='number' step='0.5' min='0' max='24' required />
            </div>
          </div>
        </details>
        <details class='ops-accordion surface-2' style='margin-top:8px;'>
          <summary>Role Capacity Defaults (hours/week)</summary>
          <div class='form-grid' style='padding:8px 10px;'>
            <div class='field'>
              <label for='opsCapAm'>AM Capacity (hours/week)</label>
              <input id='opsCapAm' type='number' step='0.5' min='1' max='80' required />
            </div>
            <div class='field'>
              <label for='opsCapCm'>CM Capacity (hours/week)</label>
              <input id='opsCapCm' type='number' step='0.5' min='1' max='80' required />
            </div>
            <div class='field'>
              <label for='opsCapCc'>CC Capacity (hours/week)</label>
              <input id='opsCapCc' type='number' step='0.5' min='1' max='80' required />
            </div>
            <div class='field'>
              <label for='opsCapDn'>DN Capacity (hours/week)</label>
              <input id='opsCapDn' type='number' step='0.5' min='1' max='80' required />
            </div>
            <div class='field'>
              <label for='opsCapMm'>MM Capacity (hours/week)</label>
              <input id='opsCapMm' type='number' step='0.5' min='1' max='80' required />
            </div>
          </div>
        </details>
        <details class='ops-accordion surface-2' style='margin-top:8px;'>
          <summary>Timeline Turnaround Defaults (days)</summary>
          <div class='form-grid' style='padding:8px 10px;'>
            <div class='field'>
              <label for='opsTimelineInterviewWeeks'>Interview Week Offset (after KO)</label>
              <input id='opsTimelineInterviewWeeks' type='number' min='1' max='8' required />
            </div>
            <div class='field'>
              <label for='opsTimelineWriting'>Writing Turnaround (working days)</label>
              <input id='opsTimelineWriting' type='number' min='1' max='40' required />
            </div>
            <div class='field'>
              <label for='opsTimelineInternalReview'>Internal Review Turnaround (working days)</label>
              <input id='opsTimelineInternalReview' type='number' min='1' max='20' required />
            </div>
            <div class='field'>
              <label for='opsTimelineClientReview'>Client Review Turnaround (working days)</label>
              <input id='opsTimelineClientReview' type='number' min='1' max='30' required />
            </div>
            <div class='field'>
              <label for='opsTimelinePublish'>Publish Turnaround After Client Review (working days)</label>
              <input id='opsTimelinePublish' type='number' min='0' max='10' required />
            </div>
            <div class='field'>
              <label for='opsTimelinePromotion'>Promotion Turnaround (calendar days)</label>
              <input id='opsTimelinePromotion' type='number' min='1' max='120' required />
            </div>
            <div class='field'>
              <label for='opsTimelineReporting'>Reporting Turnaround (calendar days)</label>
              <input id='opsTimelineReporting' type='number' min='1' max='60' required />
            </div>
          </div>
        </details>
        <details class='ops-accordion surface-2' style='margin-top:8px;'>
          <summary>Health Buffer Thresholds (working days)</summary>
          <div class='form-grid' style='padding:8px 10px;'>
            <div class='field'>
              <label for='opsHealthStepDefault'>Step Buffer Default</label>
              <input id='opsHealthStepDefault' type='number' min='0' max='90' required />
            </div>
            <div class='field'>
              <label for='opsHealthDeliverablePlanning'>Deliverable Planning Buffer</label>
              <input id='opsHealthDeliverablePlanning' type='number' min='0' max='90' required />
            </div>
            <div class='field'>
              <label for='opsHealthDeliverableProduction'>Deliverable Production Buffer</label>
              <input id='opsHealthDeliverableProduction' type='number' min='0' max='90' required />
            </div>
            <div class='field'>
              <label for='opsHealthDeliverablePromotion'>Deliverable Promotion Buffer</label>
              <input id='opsHealthDeliverablePromotion' type='number' min='0' max='90' required />
            </div>
            <div class='field'>
              <label for='opsHealthDeliverableReporting'>Deliverable Reporting Buffer</label>
              <input id='opsHealthDeliverableReporting' type='number' min='0' max='90' required />
            </div>
            <div class='field'>
              <label for='opsHealthCampaignDefault'>Campaign Buffer Default</label>
              <input id='opsHealthCampaignDefault' type='number' min='0' max='90' required />
            </div>
            <div class='field'>
              <label for='opsHealthScopeDefault'>Scope Buffer Default</label>
              <input id='opsHealthScopeDefault' type='number' min='0' max='90' required />
            </div>
          </div>
        </details>
        <details class='ops-accordion surface-2' style='margin-top:8px;'>
          <summary>Progress Segment Order</summary>
          <div class='form-grid' style='padding:8px 10px;'>
            <div class='field'><label for='opsProgressOrder1'>Position 1</label><select id='opsProgressOrder1'></select></div>
            <div class='field'><label for='opsProgressOrder2'>Position 2</label><select id='opsProgressOrder2'></select></div>
            <div class='field'><label for='opsProgressOrder3'>Position 3</label><select id='opsProgressOrder3'></select></div>
            <div class='field'><label for='opsProgressOrder4'>Position 4</label><select id='opsProgressOrder4'></select></div>
            <div class='field'><label for='opsProgressOrder5'>Position 5</label><select id='opsProgressOrder5'></select></div>
            <div class='field'><label for='opsProgressOrder6'>Position 6</label><select id='opsProgressOrder6'></select></div>
            <div class='field'><label for='opsProgressOrder7'>Position 7</label><select id='opsProgressOrder7'></select></div>
            <div class='field'><label for='opsProgressOrder8'>Position 8</label><select id='opsProgressOrder8'></select></div>
          </div>
        </details>
        <div class='actions'>
          <button class='primary' type='submit'>Save Defaults</button>
        </div>
      </form>
    </section>

    <section class='card' id='sectionRolePermissions'>
      <div class='section-head'>
        <h3>Role Permissions</h3>
        <span id='rolePermissionsMeta' class='muted'>Head of Ops can configure screen and control permissions.</span>
      </div>
      <form id='rolePermissionsForm' onsubmit='saveRolePermissions(event)'>
        <div id='rolePermissionsBody' class='sub'>Loading role permissions...</div>
        <div class='actions'>
          <button class='primary' type='submit'>Save Permissions</button>
        </div>
      </form>
    </section>

    <section class='card' id='sectionCardModules'>
      <div class='section-head'>
        <h3>Card Module Visibility</h3>
        <span id='cardModulesMeta' class='muted'>Superadmin can choose which fields appear on each object card.</span>
      </div>
      <form id='cardModulesForm' onsubmit='saveCardModuleSettings(event)'>
        <div id='cardModulesBody' class='sub'>Loading card module settings...</div>
        <div class='actions'>
          <button class='primary' type='submit'>Save Card Settings</button>
        </div>
      </form>
    </section>

    <section class='card' id='sectionListModules'>
      <div class='section-head'>
        <h3>List Module Visibility</h3>
        <span id='listModulesMeta' class='muted'>Superadmin can choose which fields appear in list rows for each object type.</span>
      </div>
      <form id='listModulesForm' onsubmit='saveListModuleSettings(event)'>
        <div id='listModulesBody' class='sub'>Loading list module settings...</div>
        <div class='actions'>
          <button class='primary' type='submit'>Save List Settings</button>
        </div>
      </form>
    </section>

    <section class='card' id='sectionAdminUsers'>
      <div class='section-head'>
        <h3>User Management</h3>
        <span id='adminUsersMeta' class='muted'>Add users and assign roles.</span>
      </div>
      <form id='adminUserCreateForm' onsubmit='createAdminUser(event)'>
        <div class='admin-grid'>
          <div class='field'>
            <label for='adminUserName'>Full name</label>
            <input id='adminUserName' type='text' required />
          </div>
          <div class='field'>
            <label for='adminUserEmail'>Email</label>
            <input id='adminUserEmail' type='email' required />
          </div>
          <div class='field'>
            <label for='adminUserTeam'>Primary team</label>
            <select id='adminUserTeam'></select>
          </div>
          <div class='field'>
            <label for='adminUserSeniority'>Seniority</label>
            <select id='adminUserSeniority'></select>
          </div>
          <div class='field'>
            <label for='adminUserAppRole'>App role</label>
            <select id='adminUserAppRole'></select>
          </div>
        </div>
        <div class='actions'>
          <button class='primary' type='submit'>Add User</button>
        </div>
      </form>
      <div id='adminUsersBody' class='stack-md' style='margin-top:8px;'></div>
    </section>

    <section class='card' id='sectionObjectRelationships'>
      <div class='section-head'>
        <h3>Object Relationships</h3>
        <span id='objectRelationshipsMeta' class='muted'>Canonical parent/child map.</span>
      </div>
      <div id='objectRelationshipsBody' class='stack-md'></div>
    </section>

    <section class='card' id='sectionHistory'>
      <h3 style='margin-top:0;'>Deliverable Audit Trail</h3>
      <div class='sub' id='historyHeader'>Select a deliverable context by generating campaigns and transitions.</div>
      <div class='actions'>
        <label for='historyDeliverableSelect' class='sub'>Deliverable:</label>
        <select id='historyDeliverableSelect' onchange='onHistorySelectionChange()'></select>
      </div>
      <div class='activity-risk-grid' style='margin-top:10px;'>
        <div>
          <h4 class='timeline-title'>Activity Timeline</h4>
          <div id='activityBody' class='activity-list'></div>
        </div>
        <div>
          <h4 class='timeline-title'>Risk Flags</h4>
          <div id='reviewsBody' class='risk-flag-list'></div>
        </div>
      </div>
    </section>

    <section class='row' id='sectionCapacityRisk'>
      <article class='card' id='sectionSystemRisks'>
        <h3>System Risks</h3>
        <table>
          <thead><tr><th>Severity</th><th>Code</th><th>Open</th></tr></thead>
          <tbody id='risksBody'></tbody>
        </table>
      </article>
    </section>

    <section class='card' id='sectionCapacity'>
      <h3>Capacity Ledger</h3>
      <div class='capacity-controls'>
        <button id='capacityWeekBtn' onclick='setCapacityView("day")'>Week</button>
        <button id='capacityMonthBtn' onclick='setCapacityView("month")' class='primary'>Month (4w)</button>
        <button id='capacityQuarterBtn' onclick='setCapacityView("quarter")'>Quarter (13w)</button>
        <button onclick='snapCapacityToToday()'>Today</button>
        <button onclick='shiftCapacityWindow(-1)'>Prev</button>
        <button onclick='shiftCapacityWindow(1)'>Next</button>
        <label class='sub' for='capacityShowItems'>Show assigned items</label>
        <input id='capacityShowItems' type='checkbox' checked onchange='toggleCapacityItems()' />
        <span id='capacityRangeLabel' class='sub'></span>
      </div>
      <div class='capacity-wrap'>
        <table class='capacity-matrix' id='capacityMatrixTable'></table>
        <div id='capacityCellPopover' class='cap-popover hidden'></div>
      </div>
      <div id='capacityDetail' class='capacity-detail hidden'></div>
    </section>

    <section class='card' id='sectionHealthWarnings'>
      <div class='section-head'>
        <h3>Capacity & Compression Warnings</h3>
        <span id='healthWarningsCount' class='muted'></span>
      </div>
      <table>
        <thead><tr><th>Campaign</th><th>Type</th><th>Severity</th><th>Reason</th><th>Owner</th></tr></thead>
        <tbody id='healthWarningsBody'></tbody>
      </table>
    </section>

    <section class='card' id='sectionRiskConsole'>
      <h3 style='margin-top:0;'>Risk Console</h3>
      <div class='actions'>
        <button data-control='create_manual_risk' onclick='createManualRisk()'>Create Manual Risk</button>
        <button data-control='resolve_manual_risk' onclick='resolveFirstManualRisk()'>Resolve First Manual Risk</button>
        <button data-control='resolve_escalation' onclick='resolveFirstEscalation()'>Resolve First Escalation</button>
      </div>
      <table>
        <thead><tr><th>ID</th><th>Severity</th><th>Open</th><th>Details</th></tr></thead>
        <tbody id='manualRisksBody'></tbody>
      </table>
    </section>
    </main>
  </div>
  <div class='toast-wrap' id='toastWrap' aria-live='polite' aria-atomic='true'></div>
  <div id='objectPanelBackdrop' class='object-panel-backdrop hidden' onclick='closeObjectPanel()'></div>
  <aside id='objectPanel' class='object-panel-host' aria-live='polite' aria-label='Object details panel'>
    <div id='objectPanelHeader' class='object-panel-header'></div>
    <div id='objectPanelBody' class='object-panel-body'></div>
    <div id='objectPanelFooter' class='object-panel-footer'></div>
  </aside>

  <script>
    const UI_FLAGS = __UI_FLAGS__;
    const users = {
      am: null,
      ops: null,
      cm: null,
      cc: null,
      sales: null,
    };
    let selectedDeliverableId = null;
    let currentRoleFlags = null;
    let myWorkCache = null;
    let currentScreen = 'home';
    let currentRole = 'cm';
    let currentActorId = null;
    let currentActorIdentity = { team: 'client_services', seniority: 'standard', app_role: 'user' };
    let currentWorkspaceCampaignId = null;
    let currentGanttCampaignId = null;
    let currentGanttView = 'month';
    let currentGanttKinds = new Set(['campaign', 'milestone', 'stage', 'step']);
    let ganttCollapsedStageKeys = new Set();
    let ganttCollapseInitCampaignId = null;
    const ganttInitialSnapDone = new Set();
    let currentWorkspaceTab = 'overview';
    let workspaceCache = null;
    let peopleSortDirection = 'asc';
    let capacityView = 'month';
    let capacityWeeks = 4;
    let capacityGranularity = 'week';
    let capacityStartWeek = null;
    let capacityShowItems = true;
    let capacityMatrixData = null;
    let capacitySelectedCell = null;
    let capacityColumns = [];
    let capacityDisplayCells = {};
    let capacityQuarterWeekSlots = {};
    let panelOpen = false;
    let panelObjectType = '';
    let panelObjectId = '';
    let panelPayload = null;
    let campaignFilterBeforeForceReveal = null;
    let opsDefaultsCache = null;
    let demoRailMinimised = false;
    let usersDirectory = [];
    let usersById = {};
    let usersByName = {};
    let adminUsersEditableRoles = ['am', 'head_ops', 'cm', 'cc', 'dn', 'mm', 'admin', 'leadership_viewer', 'head_sales', 'client'];
    let campaignHealthByCampaignId = {};
    let currentRoleControls = null;
    const PRODUCT_TYPES = ['demand', 'amplify', 'response', 'display_only'];
    const PRODUCT_TIERS = ['bronze', 'silver', 'gold'];
    let roleFlagMatrix = null;
    let rolePermissionsEditableRoles = ['am', 'head_ops', 'cm', 'cc', 'dn', 'mm', 'admin', 'leadership_viewer', 'head_sales', 'client'];
    let CONTROL_ROLE_MAP = {
      create_deal: ['am', 'admin'],
      create_submit_deal: ['am', 'admin'],
      create_demo_deal: ['am', 'admin'],
      submit_latest_deal: ['am', 'admin'],
      ops_approve_latest_deal: ['head_ops', 'admin'],
      generate_latest_campaigns: ['head_ops', 'admin'],
      complete_next_step: ['cm', 'cc', 'ccs', 'head_ops', 'admin'],
      override_step_due: ['cm', 'head_ops', 'admin'],
      run_ops_job: ['head_ops', 'admin'],
      mark_ready_publish: ['cm', 'cc', 'admin'],
      run_sow_change: ['cm', 'am', 'head_ops', 'head_sales', 'admin'],
      request_override: ['cm', 'head_ops', 'admin'],
      approve_override: ['head_ops', 'admin'],
      refresh_data: ['am', 'cm', 'cc', 'ccs', 'head_ops', 'head_sales', 'admin'],
      advance_deliverable: ['am', 'cm', 'cc', 'head_ops', 'admin'],
      create_manual_risk: ['am', 'cm', 'head_ops', 'admin'],
      resolve_manual_risk: ['cm', 'head_ops', 'admin'],
      resolve_escalation: ['head_ops', 'admin'],
      manage_step: ['cm', 'cc', 'ccs', 'head_ops', 'admin'],
      manage_deliverable_owner: ['cm', 'head_ops', 'admin'],
      manage_step_dates: ['cm', 'head_ops', 'admin'],
      manage_deliverable_dates: ['cm', 'head_ops', 'admin'],
      edit_deliverable_stage: ['cm', 'head_ops', 'admin'],
      manage_campaign_assignments: ['head_ops', 'admin'],
      manage_campaign_status: ['cm', 'head_ops', 'admin'],
      manage_campaign_dates: ['cm', 'head_ops', 'admin'],
      delete_campaign: ['head_ops', 'admin'],
      delete_deliverable: ['head_ops', 'admin'],
      admin_add_user: ['admin'],
      admin_edit_user_name: ['admin'],
      admin_edit_user_email: ['admin'],
      admin_set_user_team: ['admin'],
      admin_set_user_seniority_manager: ['admin'],
      admin_set_user_seniority_leadership: ['admin'],
      admin_set_user_app_role_admin: ['admin'],
      admin_set_user_app_role_superadmin: ['admin'],
      admin_remove_user: ['admin'],
    };
    let IDENTITY_PERMISSIONS = { screen_flags: {}, campaign_control_permissions: {}, app_control_permissions: {}, control_permissions: {} };
    let IDENTITY_PERMISSION_DIMS = {
      teams: ['sales', 'editorial', 'marketing', 'client_services'],
      seniorities: ['standard', 'manager', 'leadership'],
      app_roles: ['user', 'admin', 'superadmin'],
    };
    const APP_CONTROL_IDS = new Set([
      'run_ops_job',
      'refresh_data',
      'admin_add_user',
      'admin_edit_user_name',
      'admin_edit_user_email',
      'admin_set_user_team',
      'admin_set_user_seniority_manager',
      'admin_set_user_seniority_leadership',
      'admin_set_user_app_role_admin',
      'admin_set_user_app_role_superadmin',
      'admin_remove_user',
    ]);
    const ROLE_FLAG_KEYS = ['show_deals_pipeline', 'show_capacity', 'show_risks', 'show_reviews', 'show_admin'];
    let productLineCount = 0;

    function canUseControl(controlId, role) {
      if (currentRoleControls && currentRoleControls instanceof Set) {
        return currentRoleControls.has(controlId);
      }
      const allowed = CONTROL_ROLE_MAP[controlId];
      if (!allowed || !allowed.length) return true;
      return allowed.includes(role);
    }

    function isAppControlId(controlId) {
      const id = String(controlId || '');
      return id.startsWith('admin_') || APP_CONTROL_IDS.has(id);
    }

    function getFilterValue(id) {
      const el = document.getElementById(id);
      return (el?.value || '').trim().toLowerCase();
    }

    function getMultiFilterValues(id) {
      const el = document.getElementById(id);
      if (!(el instanceof HTMLSelectElement)) return [];
      return Array.from(el.selectedOptions || [])
        .map(option => String(option?.value || '').trim())
        .filter(Boolean);
    }

    function selectedUserFilterSet() {
      return new Set(getMultiFilterValues('qUsers'));
    }

    function selectedUserFilterLogic() {
      const el = document.getElementById('qUsersLogic');
      const value = String(el?.value || 'or').trim().toLowerCase();
      return value === 'and' ? 'and' : 'or';
    }

    function hasSelectedUserMatch(userIds = [], selectedUserIds = new Set()) {
      if (!(selectedUserIds instanceof Set) || !selectedUserIds.size) return true;
      const selected = Array.from(selectedUserIds);
      const available = new Set((Array.isArray(userIds) ? userIds : []).map(userId => String(userId || '').trim()).filter(Boolean));
      const logic = selectedUserFilterLogic();
      if (logic === 'and') return selected.every(userId => available.has(String(userId || '').trim()));
      return selected.some(userId => available.has(String(userId || '').trim()));
    }

    function campaignUserIds(campaign = {}) {
      const ids = new Set();
      const assigned = Array.isArray(campaign?.assigned_users) ? campaign.assigned_users : [];
      for (const user of assigned) {
        const userId = String(user?.user_id || user?.id || '').trim();
        if (userId) ids.add(userId);
      }
      const owners = Array.isArray(campaign?.owner_user_ids) ? campaign.owner_user_ids : [];
      for (const userId of owners) {
        const value = String(userId || '').trim();
        if (value) ids.add(value);
      }
      return Array.from(ids);
    }

    function campaignMatchesUserFilter(campaign = {}, selectedUserIds = new Set()) {
      if (!(selectedUserIds instanceof Set) || !selectedUserIds.size) return true;
      return hasSelectedUserMatch(campaignUserIds(campaign), selectedUserIds);
    }

    function scopeMatchesUserFilter(scope = {}, selectedUserIds = new Set()) {
      if (!(selectedUserIds instanceof Set) || !selectedUserIds.size) return true;
      const directIds = [
        scope?.am_user?.user_id,
        scope?.am_user_id,
        scope?.assigned_cm_user_id,
        scope?.assigned_cc_user_id,
        scope?.assigned_ccs_user_id,
      ]
        .map(value => String(value || '').trim())
        .filter(Boolean);
      if (hasSelectedUserMatch(directIds, selectedUserIds)) return true;
      const campaigns = Array.isArray(scope?.campaigns) ? scope.campaigns : [];
      return campaigns.some(campaign => campaignMatchesUserFilter(campaign, selectedUserIds));
    }

    function populateUserQuickFilter() {
      const select = document.getElementById('qUsers');
      if (!(select instanceof HTMLSelectElement)) return;
      const selected = new Set(getMultiFilterValues('qUsers'));
      const users = [...(Array.isArray(usersDirectory) ? usersDirectory : [])]
        .filter(user => String(user?.id || '').trim())
        .sort((a, b) => String(a?.name || a?.full_name || a?.email || a?.id || '').localeCompare(String(b?.name || b?.full_name || b?.email || b?.id || '')));
      if (!users.length) {
        select.innerHTML = "<option value='' disabled>No users available</option>";
        renderUserQuickFilterDropdown([], new Set());
        return;
      }
      select.innerHTML = users.map(user => {
        const userId = String(user?.id || '').trim();
        const label = String(user?.name || user?.full_name || user?.email || userId).trim() || userId;
        const selectedAttr = selected.has(userId) ? ' selected' : '';
        return `<option value="${userId.replace(/"/g, '&quot;')}"${selectedAttr}>${escapeHtml(label)}</option>`;
      }).join('');
      renderUserQuickFilterDropdown(users, selected);
    }

    function updateUserQuickFilterButtonLabel(selectedCount = 0) {
      const button = document.getElementById('qUsersButton');
      if (!(button instanceof HTMLButtonElement)) return;
      if (!selectedCount) {
        button.textContent = 'All users';
        return;
      }
      button.textContent = selectedCount === 1 ? '1 user selected' : `${selectedCount} users selected`;
    }

    function renderUserQuickFilterDropdown(users = [], selected = new Set()) {
      const menu = document.getElementById('qUsersMenu');
      if (!(menu instanceof HTMLElement)) return;
      if (!users.length) {
        menu.innerHTML = "<div class='multi-filter-empty'>No users available</div>";
        updateUserQuickFilterButtonLabel(0);
        return;
      }
      menu.innerHTML = users.map(user => {
        const userId = String(user?.id || '').trim();
        const label = String(user?.name || user?.full_name || user?.email || userId).trim() || userId;
        const checked = selected.has(userId) ? 'checked' : '';
        return `
          <label class='multi-filter-option'>
            <input type='checkbox' data-user-filter-id='${userId.replace(/"/g, '&quot;')}' ${checked} onchange='toggleUserQuickFilterOption(this)' />
            <span>${escapeHtml(label)}</span>
          </label>
        `;
      }).join('');
      updateUserQuickFilterButtonLabel(selected.size);
    }

    function toggleUsersDropdown(event) {
      if (event) event.stopPropagation();
      const menu = document.getElementById('qUsersMenu');
      const button = document.getElementById('qUsersButton');
      if (!(menu instanceof HTMLElement) || !(button instanceof HTMLButtonElement)) return;
      const opening = menu.classList.contains('hidden');
      menu.classList.toggle('hidden', !opening);
      button.setAttribute('aria-expanded', opening ? 'true' : 'false');
    }

    function closeUsersDropdown() {
      const menu = document.getElementById('qUsersMenu');
      const button = document.getElementById('qUsersButton');
      if (!(menu instanceof HTMLElement) || !(button instanceof HTMLButtonElement)) return;
      menu.classList.add('hidden');
      button.setAttribute('aria-expanded', 'false');
    }

    function toggleUserQuickFilterOption(inputEl) {
      const userId = String(inputEl?.dataset?.userFilterId || '').trim();
      const checked = !!inputEl?.checked;
      const select = document.getElementById('qUsers');
      if (!(select instanceof HTMLSelectElement) || !userId) return;
      const option = Array.from(select.options || []).find(opt => String(opt.value || '').trim() === userId);
      if (option) option.selected = checked;
      updateUserQuickFilterButtonLabel(getMultiFilterValues('qUsers').length);
      refreshAll();
    }

    function matchesFilter(text, filter) {
      if (!filter) return true;
      return String(text || '').toLowerCase().includes(filter);
    }

    const GLOBAL_STATUS_OPTIONS = [
      { value: 'not_started', label: 'Not started' },
      { value: 'in_progress', label: 'In Progress' },
      { value: 'on_hold', label: 'On Hold' },
      { value: 'blocked_client', label: 'Blocked: Client' },
      { value: 'blocked_internal', label: 'Blocked: Internal' },
      { value: 'blocked_dependency', label: 'Blocked: Dependency' },
      { value: 'done', label: 'Done' },
      { value: 'cancelled', label: 'Cancelled' },
    ];
    const DEFAULT_PROGRESS_SEGMENT_ORDER = [
      'done',
      'in_progress',
      'on_hold',
      'blocked_client',
      'blocked_internal',
      'blocked_dependency',
      'cancelled',
      'not_started',
    ];
    let PROGRESS_SEGMENT_ORDER = [...DEFAULT_PROGRESS_SEGMENT_ORDER];
    const GLOBAL_HEALTH_LABELS = {
      not_started: 'Not due',
      on_track: 'On Track',
      at_risk: 'At Risk',
      off_track: 'Off Track',
    };
    const MODULE_TYPE_LABELS = {
      scope: 'Scope',
      step: 'Step',
      stage: 'Stage',
      deliverable: 'Deliverable',
      campaign: 'Campaign',
      user: 'User',
      review: 'Review',
    };
    const DEFAULT_CARD_MODULE_CONFIG = {
      scope: {
        subtitle: true, description: false, progress: false, key_values: true, list: true, tags: true, status_badge: true, avatar_stack: true, due_date: true, actions: true,
        brand_name: true, scope_id: true, scope_status: true, scope_health: true, timeframe: true, am_owner: true, client_contact: true, products: true, sow_attachment: true, campaigns: true, icp: true, objective: true, messaging: true,
      },
      campaign: {
        subtitle: true, description: false, progress: true, key_values: true, list: true, tags: true, status_badge: true, avatar_stack: true, due_date: true, actions: true,
        campaign_status: true, campaign_health: true, owner: true, demand_track: true, timeframe: true, users_assigned: true, scope_id: true, campaign_id: true, deliverables: true, work: true,
      },
      deliverable: {
        subtitle: true, description: false, progress: false, key_values: true, list: false, tags: true, status_badge: true, avatar_stack: true, due_date: true, actions: true,
        deliverable_status: true, owner: true, timeframe: true, campaign_name: true, deliverable_id: true, stage: true,
      },
      stage: {
        subtitle: true, description: false, progress: true, key_values: true, list: true, tags: true, status_badge: true, avatar_stack: false, due_date: true, actions: true,
        stage_status: true, stage_health: true, timeframe: true, campaign_name: true, stage_id: true, steps: true,
      },
      step: {
        subtitle: true, description: true, progress: false, key_values: true, list: false, tags: true, status_badge: true, avatar_stack: true, due_date: true, actions: true,
        step_status: true, step_health: true, timeframe: true, owner: true, step_id: true, assigned_users: true, campaign_ref: true, linked_deliverable: true, note: true,
      },
    };
    const MODULE_FIELD_OPTIONS = {
      scope: [
        { key: 'subtitle', label: 'Subtitle' },
        { key: 'description', label: 'Description' },
        { key: 'progress', label: 'Progress bar' },
        { key: 'key_values', label: 'Key-value section' },
        { key: 'list', label: 'List sections' },
        { key: 'tags', label: 'Tags' },
        { key: 'status_badge', label: 'Status badge (footer)' },
        { key: 'avatar_stack', label: 'Avatar stack (footer)' },
        { key: 'due_date', label: 'Due date (footer)' },
        { key: 'actions', label: 'Actions (footer)' },
        { key: 'brand_name', label: 'Brand name' },
        { key: 'scope_id', label: 'Scope ID' },
        { key: 'scope_status', label: 'Scope status' },
        { key: 'scope_health', label: 'Scope health' },
        { key: 'timeframe', label: 'Timeframe' },
        { key: 'am_owner', label: 'AM owner' },
        { key: 'client_contact', label: 'Client contact' },
        { key: 'products', label: 'Products' },
        { key: 'sow_attachment', label: 'SOW attachment' },
        { key: 'campaigns', label: 'Campaigns accordion' },
        { key: 'icp', label: 'ICP accordion' },
        { key: 'objective', label: 'Campaign objective accordion' },
        { key: 'messaging', label: 'Messaging accordion' },
      ],
      campaign: [
        { key: 'subtitle', label: 'Subtitle' },
        { key: 'description', label: 'Description' },
        { key: 'progress', label: 'Progress bar' },
        { key: 'key_values', label: 'Key-value section' },
        { key: 'list', label: 'List sections' },
        { key: 'tags', label: 'Tags' },
        { key: 'status_badge', label: 'Status badge (footer)' },
        { key: 'avatar_stack', label: 'Avatar stack (footer)' },
        { key: 'due_date', label: 'Due date (footer)' },
        { key: 'actions', label: 'Actions (footer)' },
        { key: 'campaign_status', label: 'Campaign status' },
        { key: 'campaign_health', label: 'Campaign health' },
        { key: 'owner', label: 'Owner' },
        { key: 'demand_track', label: 'Demand track' },
        { key: 'timeframe', label: 'Timeframe' },
        { key: 'users_assigned', label: 'Users assigned' },
        { key: 'scope_id', label: 'Scope ID' },
        { key: 'campaign_id', label: 'Campaign ID' },
        { key: 'deliverables', label: 'Deliverables accordion' },
        { key: 'work', label: 'Work accordion' },
      ],
      deliverable: [
        { key: 'subtitle', label: 'Subtitle' },
        { key: 'description', label: 'Description' },
        { key: 'progress', label: 'Progress bar' },
        { key: 'key_values', label: 'Key-value section' },
        { key: 'list', label: 'List section' },
        { key: 'tags', label: 'Tags' },
        { key: 'status_badge', label: 'Status badge (footer)' },
        { key: 'avatar_stack', label: 'Avatar stack (footer)' },
        { key: 'due_date', label: 'Due date (footer)' },
        { key: 'actions', label: 'Actions (footer)' },
        { key: 'deliverable_status', label: 'Deliverable status' },
        { key: 'owner', label: 'Owner' },
        { key: 'timeframe', label: 'Timeframe' },
        { key: 'campaign_name', label: 'Associated campaign' },
        { key: 'deliverable_id', label: 'Deliverable ID' },
        { key: 'stage', label: 'Current stage' },
      ],
      stage: [
        { key: 'subtitle', label: 'Subtitle' },
        { key: 'description', label: 'Description' },
        { key: 'progress', label: 'Progress bar' },
        { key: 'key_values', label: 'Key-value section' },
        { key: 'list', label: 'List section' },
        { key: 'tags', label: 'Tags' },
        { key: 'status_badge', label: 'Status badge (footer)' },
        { key: 'avatar_stack', label: 'Avatar stack (footer)' },
        { key: 'due_date', label: 'Due date (footer)' },
        { key: 'actions', label: 'Actions (footer)' },
        { key: 'stage_status', label: 'Stage status' },
        { key: 'stage_health', label: 'Stage health' },
        { key: 'timeframe', label: 'Timeframe' },
        { key: 'campaign_name', label: 'Campaign name' },
        { key: 'stage_id', label: 'Stage ID' },
        { key: 'steps', label: 'Steps list' },
      ],
      step: [
        { key: 'subtitle', label: 'Subtitle' },
        { key: 'description', label: 'Description' },
        { key: 'progress', label: 'Progress bar' },
        { key: 'key_values', label: 'Key-value section' },
        { key: 'list', label: 'List section' },
        { key: 'tags', label: 'Tags' },
        { key: 'status_badge', label: 'Status badge (footer)' },
        { key: 'avatar_stack', label: 'Avatar stack (footer)' },
        { key: 'due_date', label: 'Due date (footer)' },
        { key: 'actions', label: 'Actions (footer)' },
        { key: 'step_status', label: 'Step status' },
        { key: 'step_health', label: 'Step health' },
        { key: 'timeframe', label: 'Timeframe' },
        { key: 'owner', label: 'Owner' },
        { key: 'step_id', label: 'Step ID' },
        { key: 'assigned_users', label: 'Assigned users' },
        { key: 'campaign_ref', label: 'Campaign reference' },
        { key: 'linked_deliverable', label: 'Linked deliverable' },
        { key: 'note', label: 'Note' },
      ],
    };
    const MODULE_STRUCTURAL_KEYS = new Set([
      'subtitle', 'description', 'progress', 'key_values', 'list', 'tags',
      'status_badge', 'avatar_stack', 'due_date', 'actions',
    ]);
    const CARD_MODULE_BINDING_OPTIONS = {
      scope: {
        subtitle: ['subtitle', 'brand_name', 'products', 'client_contact', 'scope_id'],
        description: ['description', 'icp', 'objective', 'messaging'],
      },
      campaign: {
        subtitle: ['subtitle', 'scope_id', 'demand_track', 'campaign_id'],
        description: ['description', 'demand_track', 'scope_id'],
      },
      deliverable: {
        subtitle: ['subtitle', 'campaign_name', 'stage', 'deliverable_id'],
        description: ['description', 'campaign_name', 'stage'],
      },
      stage: {
        subtitle: ['subtitle', 'campaign_name', 'stage_id'],
        description: ['description', 'campaign_name', 'stage_id'],
      },
      step: {
        subtitle: ['subtitle', 'campaign_ref', 'linked_deliverable', 'step_id'],
        description: ['description', 'linked_deliverable', 'campaign_ref', 'note'],
      },
    };
    function buildDefaultCardModuleBindings() {
      const bindings = {};
      for (const [moduleType, options] of Object.entries(MODULE_FIELD_OPTIONS || {})) {
        bindings[moduleType] = {};
        for (const opt of (options || [])) {
          const key = String(opt?.key || '').trim();
          if (!key) continue;
          bindings[moduleType][key] = key;
        }
      }
      return bindings;
    }
    const DEFAULT_CARD_MODULE_BINDINGS = buildDefaultCardModuleBindings();
    let CARD_MODULE_CONFIG = JSON.parse(JSON.stringify(DEFAULT_CARD_MODULE_CONFIG));
    let CARD_MODULE_BINDINGS = JSON.parse(JSON.stringify(DEFAULT_CARD_MODULE_BINDINGS));
    const DEFAULT_LIST_MODULE_CONFIG = {
      scope: { icon: true, title: true, plus_button: true, type_tag: true, progress: true, status: true, health: true, owner: true, avatars: true, context_id: false, options: true },
      campaign: { icon: true, title: true, plus_button: true, type_tag: true, progress: true, status: true, health: true, owner: true, avatars: true, context_id: true, options: true },
      deliverable: { icon: true, title: true, plus_button: false, type_tag: true, progress: false, status: true, health: false, owner: true, avatars: true, context_id: true, options: true },
      stage: { icon: true, title: true, plus_button: true, type_tag: true, progress: true, status: true, health: true, owner: false, avatars: false, context_id: true, options: true },
      step: { icon: true, title: true, plus_button: false, type_tag: true, progress: false, status: true, health: true, owner: true, avatars: true, context_id: true, options: true },
    };
    const LIST_FIELD_OPTIONS = {
      scope: [
        { key: 'icon', label: 'Icon', group: 'left', format: 'icon' }, { key: 'title', label: 'Title', group: 'left', format: 'text' }, { key: 'plus_button', label: 'Plus/minus', group: 'left', format: 'button' }, { key: 'type_tag', label: 'Type tag', group: 'left', format: 'tag' },
        { key: 'progress', label: 'Progress', group: 'middle', format: 'progress bar' }, { key: 'status', label: 'Status', group: 'middle', format: 'status tag' }, { key: 'health', label: 'Health', group: 'middle', format: 'health tag' }, { key: 'owner', label: 'Owner', group: 'middle', format: 'user pill' },
        { key: 'avatars', label: 'User avatars', group: 'right', format: 'avatar pills' }, { key: 'context_id', label: 'Context ID', group: 'right', format: 'id/code' }, { key: 'options', label: 'Options menu', group: 'right', format: 'menu button' },
      ],
      campaign: [
        { key: 'icon', label: 'Icon', group: 'left', format: 'icon' }, { key: 'title', label: 'Title', group: 'left', format: 'text' }, { key: 'plus_button', label: 'Plus/minus', group: 'left', format: 'button' }, { key: 'type_tag', label: 'Type tag', group: 'left', format: 'tag' },
        { key: 'progress', label: 'Progress', group: 'middle', format: 'progress bar' }, { key: 'status', label: 'Status', group: 'middle', format: 'status tag' }, { key: 'health', label: 'Health', group: 'middle', format: 'health tag' }, { key: 'owner', label: 'Owner', group: 'middle', format: 'user pill' },
        { key: 'avatars', label: 'User avatars', group: 'right', format: 'avatar pills' }, { key: 'context_id', label: 'Context ID', group: 'right', format: 'id/code' }, { key: 'options', label: 'Options menu', group: 'right', format: 'menu button' },
      ],
      deliverable: [
        { key: 'icon', label: 'Icon', group: 'left', format: 'icon' }, { key: 'title', label: 'Title', group: 'left', format: 'text' }, { key: 'plus_button', label: 'Plus/minus', group: 'left', format: 'button' }, { key: 'type_tag', label: 'Type tag', group: 'left', format: 'tag' },
        { key: 'progress', label: 'Progress', group: 'middle', format: 'progress bar' }, { key: 'status', label: 'Status', group: 'middle', format: 'status tag' }, { key: 'health', label: 'Health', group: 'middle', format: 'health tag' }, { key: 'owner', label: 'Owner', group: 'middle', format: 'user pill' },
        { key: 'avatars', label: 'User avatars', group: 'right', format: 'avatar pills' }, { key: 'context_id', label: 'Context ID', group: 'right', format: 'id/code' }, { key: 'options', label: 'Options menu', group: 'right', format: 'menu button' },
      ],
      stage: [
        { key: 'icon', label: 'Icon', group: 'left', format: 'icon' }, { key: 'title', label: 'Title', group: 'left', format: 'text' }, { key: 'plus_button', label: 'Plus/minus', group: 'left', format: 'button' }, { key: 'type_tag', label: 'Type tag', group: 'left', format: 'tag' },
        { key: 'progress', label: 'Progress', group: 'middle', format: 'progress bar' }, { key: 'status', label: 'Status', group: 'middle', format: 'status tag' }, { key: 'health', label: 'Health', group: 'middle', format: 'health tag' }, { key: 'owner', label: 'Owner', group: 'middle', format: 'user pill' },
        { key: 'avatars', label: 'User avatars', group: 'right', format: 'avatar pills' }, { key: 'context_id', label: 'Context ID', group: 'right', format: 'id/code' }, { key: 'options', label: 'Options menu', group: 'right', format: 'menu button' },
      ],
      step: [
        { key: 'icon', label: 'Icon', group: 'left', format: 'icon' }, { key: 'title', label: 'Title', group: 'left', format: 'text' }, { key: 'plus_button', label: 'Plus/minus', group: 'left', format: 'button' }, { key: 'type_tag', label: 'Type tag', group: 'left', format: 'tag' },
        { key: 'progress', label: 'Progress', group: 'middle', format: 'progress bar' }, { key: 'status', label: 'Status', group: 'middle', format: 'status tag' }, { key: 'health', label: 'Health', group: 'middle', format: 'health tag' }, { key: 'owner', label: 'Owner', group: 'middle', format: 'user pill' },
        { key: 'avatars', label: 'User avatars', group: 'right', format: 'avatar pills' }, { key: 'context_id', label: 'Context ID', group: 'right', format: 'id/code' }, { key: 'options', label: 'Options menu', group: 'right', format: 'menu button' },
      ],
    };
    const LIST_MODULE_BINDING_OPTIONS = {
      scope: { title: ['title', 'name', 'client_name', 'id'], context_id: ['context_id', 'scope_id', 'id'] },
      campaign: { title: ['title', 'name', 'campaign_name', 'id'], status: ['status', 'campaign_status'], health: ['health', 'campaign_health'], context_id: ['context_id', 'scope_id', 'campaign_id', 'id'] },
      deliverable: { title: ['title', 'name', 'deliverable_name', 'id'], status: ['status', 'deliverable_status'], context_id: ['context_id', 'campaign_id', 'id'] },
      stage: { title: ['title', 'name', 'stage_name', 'id'], status: ['status', 'stage_status'], health: ['health', 'stage_health'], context_id: ['context_id', 'campaign_id', 'id'] },
      step: { title: ['title', 'name', 'step_name', 'id'], status: ['status', 'step_status'], health: ['health', 'step_health'], context_id: ['context_id', 'campaign_id', 'id'] },
    };
    function buildDefaultListModuleBindings() {
      const bindings = {};
      for (const [moduleType, options] of Object.entries(LIST_FIELD_OPTIONS || {})) {
        bindings[moduleType] = {};
        for (const opt of (options || [])) {
          const key = String(opt?.key || '').trim();
          if (!key) continue;
          bindings[moduleType][key] = key;
        }
      }
      return bindings;
    }
    const DEFAULT_LIST_MODULE_BINDINGS = buildDefaultListModuleBindings();
    let LIST_MODULE_CONFIG = JSON.parse(JSON.stringify(DEFAULT_LIST_MODULE_CONFIG));
    let LIST_MODULE_BINDINGS = JSON.parse(JSON.stringify(DEFAULT_LIST_MODULE_BINDINGS));
    const LIST_EXPANDED_ROW_KEYS = new Set();
    const LIST_ROWS_CACHE = {
      campaigns: [],
      deals: [],
    };
    const MODULE_EDIT_STATE = {};

    function normalizeCardModuleConfig(raw) {
      const out = JSON.parse(JSON.stringify(DEFAULT_CARD_MODULE_CONFIG));
      if (!raw || typeof raw !== 'object') return out;
      for (const [moduleType, slots] of Object.entries(out)) {
        const incoming = raw[moduleType];
        if (!incoming || typeof incoming !== 'object') continue;
        for (const key of Object.keys(slots)) {
          if (typeof incoming[key] === 'boolean') out[moduleType][key] = incoming[key];
        }
      }
      return out;
    }

    function normalizeCardModuleBindings(raw) {
      const out = JSON.parse(JSON.stringify(DEFAULT_CARD_MODULE_BINDINGS));
      if (!raw || typeof raw !== 'object') return out;
      for (const moduleType of Object.keys(out)) {
        const incomingModule = raw[moduleType];
        if (!incomingModule || typeof incomingModule !== 'object') continue;
        for (const slotKey of Object.keys(out[moduleType])) {
          const candidate = incomingModule[slotKey];
          if (typeof candidate === 'string' && candidate.trim()) out[moduleType][slotKey] = candidate.trim();
        }
      }
      return out;
    }

    function normalizeListModuleConfig(raw) {
      const out = JSON.parse(JSON.stringify(DEFAULT_LIST_MODULE_CONFIG));
      if (!raw || typeof raw !== 'object') return out;
      for (const [moduleType, slots] of Object.entries(out)) {
        const incoming = raw[moduleType];
        if (!incoming || typeof incoming !== 'object') continue;
        for (const key of Object.keys(slots)) {
          if (typeof incoming[key] === 'boolean') out[moduleType][key] = incoming[key];
        }
      }
      return out;
    }

    function normalizeListModuleBindings(raw) {
      const out = JSON.parse(JSON.stringify(DEFAULT_LIST_MODULE_BINDINGS));
      if (!raw || typeof raw !== 'object') return out;
      for (const moduleType of Object.keys(out)) {
        const incomingModule = raw[moduleType];
        if (!incomingModule || typeof incomingModule !== 'object') continue;
        for (const slotKey of Object.keys(out[moduleType])) {
          const candidate = incomingModule[slotKey];
          if (typeof candidate === 'string' && candidate.trim()) out[moduleType][slotKey] = candidate.trim();
        }
      }
      return out;
    }

    function cardSlotEnabled(moduleType, slotKey) {
      const moduleCfg = CARD_MODULE_CONFIG[String(moduleType || '').toLowerCase()] || DEFAULT_CARD_MODULE_CONFIG[String(moduleType || '').toLowerCase()] || {};
      if (typeof moduleCfg[slotKey] === 'boolean') return moduleCfg[slotKey];
      const fallback = DEFAULT_CARD_MODULE_CONFIG[String(moduleType || '').toLowerCase()] || {};
      return typeof fallback[slotKey] === 'boolean' ? fallback[slotKey] : true;
    }

    function listSlotEnabled(moduleType, slotKey) {
      const moduleCfg = LIST_MODULE_CONFIG[String(moduleType || '').toLowerCase()] || DEFAULT_LIST_MODULE_CONFIG[String(moduleType || '').toLowerCase()] || {};
      if (typeof moduleCfg[slotKey] === 'boolean') return moduleCfg[slotKey];
      const fallback = DEFAULT_LIST_MODULE_CONFIG[String(moduleType || '').toLowerCase()] || {};
      return typeof fallback[slotKey] === 'boolean' ? fallback[slotKey] : true;
    }

    function listBoundField(moduleType, slotKey) {
      const t = String(moduleType || '').toLowerCase();
      return String(LIST_MODULE_BINDINGS?.[t]?.[slotKey] || slotKey);
    }

    function moduleIcon(moduleType) {
      const key = String(moduleType || '').toLowerCase();
      if (key === 'campaign') return "<svg viewBox='0 0 16 16' aria-hidden='true'><rect x='2' y='5' width='5' height='8' rx='1' fill='currentColor' opacity='0.8'/><rect x='9' y='2' width='5' height='11' rx='1' fill='currentColor' opacity='0.45'/></svg>";
      if (key === 'deliverable') return "<svg viewBox='0 0 16 16' aria-hidden='true'><rect x='3' y='2' width='10' height='12' rx='1.5' stroke='currentColor' fill='none'/><line x1='5' y1='6' x2='11' y2='6' stroke='currentColor'/><line x1='5' y1='9' x2='11' y2='9' stroke='currentColor'/></svg>";
      if (key === 'step') return "<svg viewBox='0 0 16 16' aria-hidden='true'><circle cx='4' cy='5' r='1.4' fill='currentColor'/><rect x='7' y='4' width='6' height='2' rx='1' fill='currentColor'/><circle cx='4' cy='10.5' r='1.4' fill='currentColor' opacity='0.6'/><rect x='7' y='9.5' width='6' height='2' rx='1' fill='currentColor' opacity='0.6'/></svg>";
      if (key === 'stage') return "<svg viewBox='0 0 16 16' aria-hidden='true'><path d='M2 3h12v3H2zM2 7h8v3H2zM2 11h5v2H2z' fill='currentColor'/></svg>";
      if (key === 'scope') return "<svg viewBox='0 0 16 16' aria-hidden='true'><path d='M3 2h7l3 3v9H3z' stroke='currentColor' fill='none'/><path d='M10 2v3h3' stroke='currentColor' fill='none'/></svg>";
      return "<svg viewBox='0 0 16 16' aria-hidden='true'><circle cx='8' cy='8' r='5' fill='currentColor' opacity='0.7'/></svg>";
    }

    function normalizeStatusValue(value) {
      const v = String(value || '').toLowerCase().trim();
      if (v === 'draft') return 'not_started';
      if (v === 'active' || v === 'live') return 'in_progress';
      if (v === 'complete') return 'done';
      if (v === 'planned') return 'not_started';
      return v;
    }

    function statusLabel(value) {
      const v = normalizeStatusValue(value);
      const hit = GLOBAL_STATUS_OPTIONS.find(o => o.value === v);
      return hit ? hit.label : (value || 'Not started');
    }

    function normalizeProgressSegmentOrder(order) {
      const allowed = new Set(DEFAULT_PROGRESS_SEGMENT_ORDER);
      const incoming = Array.isArray(order) ? order.map(v => normalizeStatusValue(v)).filter(v => allowed.has(v)) : [];
      const unique = [];
      for (const v of incoming) {
        if (!unique.includes(v)) unique.push(v);
      }
      for (const v of DEFAULT_PROGRESS_SEGMENT_ORDER) {
        if (!unique.includes(v)) unique.push(v);
      }
      return unique.slice(0, DEFAULT_PROGRESS_SEGMENT_ORDER.length);
    }

    function statusChip(value) {
      const v = normalizeStatusValue(value);
      const display = statusLabel(v);
      let cls = 'tag neutral';
      if (v === 'not_started') cls = 'tag neutral';
      else if (v === 'in_progress') cls = 'tag status-in-progress';
      else if (v === 'on_hold') cls = 'tag status-on-hold';
      else if (v === 'blocked_dependency') cls = 'tag status-blocked-dependency';
      else if (v === 'blocked_client' || v === 'blocked_internal') cls = 'tag status-blocked';
      else if (v === 'done') cls = 'tag status-done';
      else if (v === 'cancelled') cls = 'tag status-cancelled';
      const output = GLOBAL_STATUS_OPTIONS.find(o => o.value === v)
        ? display
        : String(value || 'Not started').replace(/_/g, ' ').replace(/\b\w/g, m => m.toUpperCase());
      return `<span class="${cls}">${output}</span>`;
    }

    function severityChip(value) {
      const v = String(value || '').toLowerCase();
      if (v === 'critical' || v === 'high') return "<span class='tag risk'>High</span>";
      if (v === 'medium') return "<span class='tag warn'>Medium</span>";
      if (v === 'low') return "<span class='tag ok'>Low</span>";
      return "<span class='tag neutral'>-</span>";
    }

    function healthChip(value) {
      const v = String(value || 'not_started').toLowerCase();
      const label = GLOBAL_HEALTH_LABELS[v] || 'Not due';
      if (v === 'off_track') return `<span class='tag risk'>${label}</span>`;
      if (v === 'at_risk') return `<span class='tag warn'>${label}</span>`;
      if (v === 'on_track') return `<span class='tag ok'>${label}</span>`;
      return `<span class='tag neutral'>${label}</span>`;
    }

    function progressStatusClass(status) {
      const v = normalizeStatusValue(status);
      if (v === 'done') return 'status-done';
      if (v === 'in_progress') return 'status-in-progress';
      if (v === 'on_hold') return 'status-on-hold';
      if (v === 'blocked_dependency') return 'status-blocked-dependency';
      if (v === 'blocked_client' || v === 'blocked_internal') return 'status-blocked';
      if (v === 'cancelled') return 'status-cancelled';
      return 'status-not-started';
    }

    function progressNeedsHatch(status) {
      const v = normalizeStatusValue(status);
      return !(v === 'done' || v === 'cancelled' || v === 'not_started');
    }

    function renderSegmentedProgress(statuses) {
      const list = Array.isArray(statuses)
        ? statuses.map(s => normalizeStatusValue(s || 'not_started'))
        : [];
      const total = list.length;
      const done = list.filter(s => s === 'done').length;
      const pct = total ? Math.round((done / total) * 100) : 0;
      if (!total) {
        return {
          done: 0,
          total: 0,
          pct: 0,
          barHtml: "<div class='progress-track segmented'></div>",
        };
      }
      const order = normalizeProgressSegmentOrder(PROGRESS_SEGMENT_ORDER);
      const counts = {};
      for (const s of list) counts[s] = (counts[s] || 0) + 1;
      const segments = order
        .filter(key => Number(counts[key] || 0) > 0)
        .map(key => {
          const count = Number(counts[key] || 0);
          const width = (count / total) * 100;
          const cls = progressStatusClass(key);
          const hatched = progressNeedsHatch(key) ? ' hatched' : '';
          return `<span class='progress-segment ${cls}${hatched}' style='width:${width}%;' title='${statusLabel(key)} ${count}/${total}'></span>`;
        })
        .join('');
      return {
        done,
        total,
        pct,
        barHtml: `<div class='progress-track segmented'>${segments}</div>`,
      };
    }

    function moduleTypePill(moduleType) {
      const key = String(moduleType || '').toLowerCase();
      return `<span class='tag ${objectTypeTagClass(key)} module-kind-pill'>${MODULE_TYPE_LABELS[key] || 'Module'}</span>`;
    }

    function objectTypeTagClass(moduleType) {
      const key = String(moduleType || '').toLowerCase();
      if (key === 'scope') return 'obj-scope';
      if (key === 'campaign') return 'obj-campaign';
      if (key === 'deliverable') return 'obj-deliverable';
      if (key === 'stage') return 'obj-stage';
      if (key === 'step') return 'obj-step';
      return 'neutral';
    }

    function moduleEditKey(moduleType, objectId) {
      const t = String(moduleType || '').toLowerCase().trim();
      const id = String(objectId || '').trim();
      if (!t || !id) return '';
      return `${t}|${id}`;
    }

    function isModuleEditing(moduleType, objectId) {
      const key = moduleEditKey(moduleType, objectId);
      return key ? !!MODULE_EDIT_STATE[key] : false;
    }

    function canEditFromModuleMenu(moduleType) {
      const key = String(moduleType || '').toLowerCase();
      if (key === 'scope' || key === 'stage') {
        return true;
      }
      if (key === 'campaign') {
        return canUseControl('manage_campaign_assignments', currentRole) || canUseControl('manage_campaign_dates', currentRole);
      }
      if (key === 'deliverable') {
        return canUseControl('manage_deliverable_owner', currentRole) || canUseControl('manage_deliverable_dates', currentRole);
      }
      if (key === 'step') {
        return canUseControl('manage_step', currentRole) || canUseControl('manage_step_dates', currentRole);
      }
      return false;
    }

    function moduleOptionsButton() {
      return `<button type='button' class='module-option-btn' data-module-options-trigger='1' aria-haspopup='menu' aria-expanded='false' aria-label='Module options' title='Options'>
        <svg viewBox='0 0 16 16' aria-hidden='true'><circle cx='4' cy='8' r='1.2' fill='currentColor'/><circle cx='8' cy='8' r='1.2' fill='currentColor'/><circle cx='12' cy='8' r='1.2' fill='currentColor'/></svg>
      </button>`;
    }

    function moduleHeadRight(moduleType, objectId = '', opts = {}) {
      const optionsButton = moduleOptionsButton();
      const canMenuEdit = canEditFromModuleMenu(moduleType);
      const editing = canMenuEdit && isModuleEditing(moduleType, objectId);
      const canDeleteCampaign = String(moduleType || '').toLowerCase() === 'campaign' && canUseControl('delete_campaign', currentRole);
      const canDeleteDeliverable = String(moduleType || '').toLowerCase() === 'deliverable' && canUseControl('delete_deliverable', currentRole);
      const menuActions = [
        `<button type='button' class='module-options-item' data-module-menu-action='open' data-module-type='${String(moduleType || '')}' data-object-id='${String(objectId || '')}'>Open</button>`,
        canMenuEdit
          ? `<button type='button' class='module-options-item' data-module-menu-action='edit' data-module-type='${String(moduleType || '')}' data-object-id='${String(objectId || '')}'>${editing ? 'Done Editing' : 'Edit'}</button>`
          : '',
        canDeleteCampaign
          ? `<button type='button' class='module-options-item danger' data-module-menu-action='delete' data-module-type='campaign' data-object-id='${String(objectId || '')}'>Delete Campaign</button>`
          : '',
        canDeleteDeliverable
          ? `<button type='button' class='module-options-item danger' data-module-menu-action='delete' data-module-type='deliverable' data-object-id='${String(objectId || '')}'>Delete Deliverable</button>`
          : '',
      ].filter(Boolean).join('');
      const editMenu = canMenuEdit
        ? `<div class='module-options-menu'>${menuActions}</div>`
        : `<div class='module-options-menu'>${menuActions || "<button type='button' class='module-options-item' disabled>No actions</button>"}</div>`;
      const closeBtn = (opts?.popover || opts?.panel) ? `<button type='button' class='ghost module-close-btn' onclick='closeObjectPanel()'>Close</button>` : '';
      const typePill = (opts?.popover || opts?.panel) ? '' : moduleTypePill(moduleType);
      const editBadge = editing ? "<span class='tag done'>Editing</span>" : '';
      return `<div class='module-head-controls'>${typePill}${editBadge}<div class='module-options' data-module-options='1' data-options-wrap='1'>${optionsButton}${editMenu}</div>${closeBtn}</div>`;
    }

    async function toggleModuleEditFromMenu(moduleType, objectId) {
      const key = moduleEditKey(moduleType, objectId);
      if (!key) return;
      const normalizedType = String(moduleType || '').toLowerCase();
      MODULE_EDIT_STATE[key] = !MODULE_EDIT_STATE[key];
      const editEnabled = !!MODULE_EDIT_STATE[key];
      if (panelOpen && panelObjectType === String(moduleType || '').toLowerCase() && panelObjectId === String(objectId || '')) {
        openObjectPanelByPayload(panelPayload || {});
        requestAnimationFrame(() => applyModuleLayoutRules(document.getElementById('objectPanel') || document));
        return;
      }
      if (currentScreen === 'campaigns') {
        await runCampaignAwareRefresh(async () => { await renderScreen(); });
      } else {
        await renderScreen();
      }
      if (panelOpen && panelObjectType === String(moduleType || '').toLowerCase() && panelObjectId === String(objectId || '')) {
        const campaignId = String(
          panelPayload?.campaign?.id
          || panelPayload?.stage?.campaign_id
          || panelPayload?.deliverable?.campaign_id
          || panelPayload?.step?.campaign_id
          || ''
        ).trim();
        const refreshed = await fetchObjectPanelPayload(moduleType, objectId, campaignId);
        if (refreshed) openObjectPanelByPayload(refreshed);
      }
      requestAnimationFrame(() => {
        if (editEnabled && normalizedType) {
          const selector = `details.module-card[data-module='${normalizedType}']${attrEqSelector('data-obj-id', String(objectId || ''))}`;
          const targetCard = document.querySelector(selector);
          if (targetCard && !targetCard.open) targetCard.open = true;
        }
        applyModuleLayoutRules();
      });
    }

    function closeAllModuleOptionMenus(exceptEl = null) {
      const menus = Array.from(document.querySelectorAll('.module-options.open, .list-options.open'));
      for (const menu of menus) {
        if (exceptEl && (menu === exceptEl || menu.contains(exceptEl))) continue;
        menu.classList.remove('open');
        const trigger = menu.querySelector('[data-module-options-trigger]');
        if (trigger) trigger.setAttribute('aria-expanded', 'false');
      }
    }

    function moduleCardOpenPath(moduleType, objectId, cardEl = null) {
      const type = String(moduleType || '').toLowerCase();
      const objId = String(objectId || '').trim();
      const campaignId = String((cardEl?.closest('.module-card')?.getAttribute('data-campaign-id') || cardEl?.getAttribute?.('data-campaign-id') || '')).trim();
      if (type === 'scope') return screenPath('deals');
      if (type === 'campaign') {
        if (!objId) return screenPath('campaigns');
        return campaignsPathWithTarget({ targetType: 'campaign', targetId: objId, campaignId: objId });
      }
      if (type === 'stage') {
        if (!objId || !campaignId) return screenPath('campaigns');
        return campaignsPathWithTarget({ targetType: 'stage', targetId: objId, campaignId, expand: 'work' });
      }
      if (type === 'deliverable') {
        if (!objId || !campaignId) return screenPath('campaigns');
        return campaignsPathWithTarget({ targetType: 'deliverable', targetId: objId, campaignId, expand: 'deliverables' });
      }
      if (type === 'step') {
        if (!objId || !campaignId) return screenPath('campaigns');
        return campaignsPathWithTarget({ targetType: 'step', targetId: objId, campaignId, expand: 'work' });
      }
      return screenPath('home');
    }

    async function handleModuleMenuAction(action, moduleType, objectId, sourceEl = null) {
      const type = String(moduleType || '').toLowerCase();
      const objId = String(objectId || '');
      const act = String(action || '').toLowerCase();
      if (!act) return;
      if (act === 'open') {
        const campaignId = String(
          sourceEl?.getAttribute?.('data-campaign-id')
          || sourceEl?.closest?.('.module-card')?.getAttribute?.('data-campaign-id')
          || ''
        ).trim();
        const payload = await fetchObjectPanelPayload(type, objId, campaignId);
        if (payload) {
          openObjectPanelByPayload(payload);
        } else {
          const path = moduleCardOpenPath(type, objId, sourceEl?.closest?.('.module-card') || null);
          if (path) window.location.href = path;
        }
        return;
      }
      if (act === 'edit') {
        await toggleModuleEditFromMenu(type, objId);
        return;
      }
      if (act === 'delete') {
        if (type === 'campaign') {
          await deleteCampaign(objId);
          return;
        }
        if (type === 'deliverable') {
          await deleteDeliverable(objId);
          return;
        }
      }
    }

    function moduleOpenButtonHtml(opts = {}) {
      if (!opts?.popover || !opts?.openPath) return '';
      const label = opts.openLabel || 'Open';
      const safePath = String(opts.openPath).replace(/"/g, '&quot;');
      return `<div class='actions module-popover-actions'><button class='primary' onclick='window.location.href="${safePath}"'>${label}</button></div>`;
    }

    function moduleAvatarStack(users = []) {
      const entries = (Array.isArray(users) ? users : []).slice(0, 4);
      if (!entries.length) return '';
      const html = entries.map(u => {
        const initials = String(u?.initials || '--');
        const name = String(u?.name || '').trim();
        return userPill(initials, false, name || null, { userId: u?.id || u?.user_id || '', roleKey: u?.role || '', team: u?.team || '' });
      }).join('');
      return `<div class='avatar-stack'>${html}</div>`;
    }

    function moduleFooterHtml(moduleType, opts = {}) {
      const type = String(moduleType || '').toLowerCase();
      const left = [];
      const right = [];
      if (cardSlotEnabled(type, 'status_badge') && opts.statusHtml) left.push(opts.statusHtml);
      if (cardSlotEnabled(type, 'avatar_stack') && opts.avatarsHtml) left.push(opts.avatarsHtml);
      if (cardSlotEnabled(type, 'due_date') && opts.dueText) right.push(`<span class='due-text'>${opts.dueText}</span>`);
      if (cardSlotEnabled(type, 'actions') && opts.actionsHtml) right.push(opts.actionsHtml);
      if (!left.length && !right.length) return '';
      return `<div class='module-footer'><div class='module-footer-left'>${left.join('')}</div><div class='module-footer-right'>${right.join('')}</div></div>`;
    }

    function listTypeTag(moduleType) {
      const key = String(moduleType || '').toLowerCase();
      return `<span class='tag ${objectTypeTagClass(key)}'>${MODULE_TYPE_LABELS[key] || 'Object'}</span>`;
    }

    function listProgressHtml(statuses = []) {
      if (!Array.isArray(statuses) || !statuses.length) return '';
      const progress = renderSegmentedProgress(statuses || []);
      return `<div class='list-row-progress'>${progress.barHtml}</div>`;
    }

    function listContextIdForRow(row) {
      const t = String(row?.module_type || '').toLowerCase();
      if (t === 'campaign') return String(row.scope_id || '').trim();
      if (t === 'stage' || t === 'deliverable' || t === 'step') return String(row.campaign_id || '').trim();
      return '';
    }

    function listObjectValue(row, slotKey) {
      const source = listBoundField(row?.module_type || '', slotKey);
      return row?.[source];
    }

    function listOptionsMenuHtml(row) {
      const moduleType = String(row?.module_type || '').toLowerCase();
      const objectId = String(row?.id || '').trim();
      const campaignId = String(row?.campaign_id || '').trim();
      const canDeleteCampaign = moduleType === 'campaign' && canUseControl('delete_campaign', currentRole);
      const canDeleteDeliverable = moduleType === 'deliverable' && canUseControl('delete_deliverable', currentRole);
      const canEdit = canEditFromModuleMenu(moduleType);
      const actions = [
        `<button type='button' class='list-options-item' data-list-menu-action='open' data-module-type='${moduleType}' data-object-id='${objectId}' data-campaign-id='${campaignId}'>Open</button>`,
        canEdit ? `<button type='button' class='list-options-item' data-list-menu-action='edit' data-module-type='${moduleType}' data-object-id='${objectId}' data-campaign-id='${campaignId}'>Edit</button>` : '',
        canDeleteCampaign ? `<button type='button' class='list-options-item danger' data-list-menu-action='delete' data-module-type='campaign' data-object-id='${objectId}' data-campaign-id='${campaignId}'>Delete Campaign</button>` : '',
        canDeleteDeliverable ? `<button type='button' class='list-options-item danger' data-list-menu-action='delete' data-module-type='deliverable' data-object-id='${objectId}' data-campaign-id='${campaignId}'>Delete Deliverable</button>` : '',
      ].filter(Boolean).join('');
      return `
        <div class='list-options' data-list-options='1' data-options-wrap='1'>
          ${moduleOptionsButton()}
          <div class='list-options-menu'>${actions || "<button type='button' class='list-options-item' disabled>No actions</button>"}</div>
        </div>
      `;
    }

    function listRowHtml(row, depth = 0) {
      const moduleType = String(row?.module_type || '').toLowerCase();
      const rowKey = String(row?.row_key || `${moduleType}:${row?.id || row?.title || Math.random()}`);
      const hasChildren = Array.isArray(row?.children) && row.children.length > 0;
      const expanded = hasChildren && LIST_EXPANDED_ROW_KEYS.has(rowKey);
      const title = String(listObjectValue(row, 'title') || row?.title || row?.name || row?.id || '-');
      const status = normalizeStatusValue(listObjectValue(row, 'status') || row?.status || '');
      const health = String(listObjectValue(row, 'health') || row?.health || '').toLowerCase();
      const ownerInitials = String(row?.owner_initials || '--').trim() || '--';
      const ownerName = String(row?.owner_name || '').trim();
      const ownerUserId = String(row?.owner_user_id || row?.next_owner_user_id || '').trim();
      const participants = Array.isArray(row?.participants) ? row.participants : [];
      const contextId = String(listObjectValue(row, 'context_id') || row?.context_id || listContextIdForRow(row) || '').trim();
      const popoverPayload = encodePopoverPayload(listRowPopoverPayload(row));
      const left = `
        ${listSlotEnabled(moduleType, 'plus_button')
          ? (hasChildren ? `<button type='button' class='list-toggle-btn' data-list-toggle='${rowKey}' aria-label='${expanded ? 'Collapse' : 'Expand'}'>${expanded ? '−' : '+'}</button>` : `<span class='list-toggle-placeholder'></span>`)
          : ''}
        ${listSlotEnabled(moduleType, 'icon') ? `<span class='module-icon'>${moduleIcon(moduleType)}</span>` : ''}
        <button type='button' class='list-title list-title-btn' data-list-open-popover='${popoverPayload}'>${escapeHtml(title)}</button>
        ${listSlotEnabled(moduleType, 'type_tag') ? listTypeTag(moduleType) : ''}
      `;
      const middle = `
        ${listSlotEnabled(moduleType, 'progress') ? listProgressHtml(row?.progress_statuses || []) : ''}
        ${listSlotEnabled(moduleType, 'status') && status ? listStatusControl(row, moduleType, status) : ''}
        ${listSlotEnabled(moduleType, 'health') && health ? healthChip(health) : ''}
        ${listSlotEnabled(moduleType, 'owner') ? `<span class='list-owner-pill'>${userPill(ownerInitials, true, ownerName || null, { userId: ownerUserId })}</span>` : ''}
      `;
      const avatarsHtml = (moduleType !== 'scope') && listSlotEnabled(moduleType, 'avatars')
        ? `<span class='list-avatar-pills'>${participants.slice(0, 3).map(p => userPill(p?.initials || '--', false, p?.name || null, { userId: p?.id || p?.user_id || '', roleKey: p?.role || '', team: p?.team || '' })).join('')}</span>`
        : '';
      const contextIdHtml = (listSlotEnabled(moduleType, 'context_id') && contextId)
        ? `<span class='list-context-id'>${escapeHtml(contextId)}</span>`
        : '';
      const optionsHtml = listSlotEnabled(moduleType, 'options') ? listOptionsMenuHtml(row) : '';
      const right = `
        <div class='list-right-avatars'>${avatarsHtml}</div>
        <div class='list-right-id'>${contextIdHtml}</div>
        <div class='list-right-options'>${optionsHtml}</div>
      `;
      const currentRow = `
        <div class='list-module-row depth-${Math.min(Math.max(Number(depth || 0), 0), 3)}'
             data-list-row='1'
             data-row-key='${rowKey}'
             data-module='${moduleType}'
             data-object-id='${escapeHtml(String(row?.id || ''))}'
             data-campaign-id='${escapeHtml(String(row?.campaign_id || ''))}'
             data-list-popover-payload='${popoverPayload}'>
          <div class='list-left'>${left}</div>
          <div class='list-middle'>${middle}</div>
          <div class='list-right'>${right}</div>
        </div>
      `;
      if (!(expanded && hasChildren)) return currentRow;
      const childrenHtml = row.children.map(child => listRowHtml(child, depth + 1)).join('');
      return `${currentRow}${childrenHtml}`;
    }

    function listRowPopoverPayload(row) {
      const moduleType = String(row?.module_type || '').toLowerCase();
      const campaignId = String(row?.campaign_id || '').trim();
      const contextId = String(row?.context_id || '').trim();
      const base = {
        module_type: moduleType,
        open_label: 'Open',
      };
      if (moduleType === 'scope') {
        const scope = {
          id: String(row?.id || ''),
          client_name: String(row?.title || row?.name || 'Scope'),
          status: normalizeStatusValue(row?.status || 'not_started'),
          health: String(row?.health || 'not_started').toLowerCase(),
          sow_start_date: row?.timeframe_start || null,
          sow_end_date: row?.timeframe_due || null,
          am_name: String(row?.owner_name || ''),
          am_initials: String(row?.owner_initials || '--'),
          campaigns: [],
        };
        return {
          ...base,
          scope,
          open_deep_link: screenPath('deals'),
          open_path: screenPath('deals'),
        };
      }
      if (moduleType === 'campaign') {
        const campaign = {
          id: String(row?.id || ''),
          campaign_id: String(row?.id || ''),
          title: String(row?.title || 'Campaign'),
          status: normalizeStatusValue(row?.status || 'not_started'),
          health: String(row?.health || 'not_started').toLowerCase(),
          timeframe_start: row?.timeframe_start || null,
          timeframe_due: row?.timeframe_due || null,
          assigned_users: [],
          scope_id: contextId || null,
          deliverables: [],
          work_steps: [],
          deliverables_summary: { total: 0, not_started: 0, in_progress: 0, done: 0 },
          work_summary: { total: 0, not_started: 0, in_progress: 0, done: 0 },
        };
        return {
          ...base,
          campaign,
          open_deep_link: campaignsPathWithTarget({ targetType: 'campaign', targetId: campaign.id, campaignId: campaign.id }),
          open_path: screenPath('campaigns'),
        };
      }
      if (moduleType === 'stage') {
        const stage = {
          id: String(row?.id || ''),
          name: String(row?.title || 'Stage'),
          status: normalizeStatusValue(row?.status || 'not_started'),
          health: String(row?.health || 'not_started').toLowerCase(),
          timeframe_start: row?.timeframe_start || null,
          timeframe_due: row?.timeframe_due || null,
          campaign_id: campaignId || null,
          campaign_name: '',
        };
        return {
          ...base,
          stage,
          campaign: campaignId ? { id: campaignId } : undefined,
          open_deep_link: campaignId
            ? campaignsPathWithTarget({ targetType: 'stage', targetId: stage.id, campaignId, expand: 'work' })
            : screenPath('campaigns'),
          open_path: screenPath('campaigns'),
        };
      }
      if (moduleType === 'deliverable') {
        const deliverable = {
          id: String(row?.id || ''),
          title: String(row?.title || 'Deliverable'),
          status: normalizeStatusValue(row?.status || 'not_started'),
          health: String(row?.health || 'not_started').toLowerCase(),
          current_start: row?.timeframe_start || null,
          current_due: row?.timeframe_due || null,
          owner_initials: String(row?.owner_initials || '--'),
          owner_name: String(row?.owner_name || ''),
          stage: String(row?.stage || ''),
          campaign_id: campaignId || null,
        };
        return {
          ...base,
          deliverable,
          campaign: campaignId ? { id: campaignId } : undefined,
          open_deep_link: campaignId
            ? campaignsPathWithTarget({ targetType: 'deliverable', targetId: deliverable.id, campaignId, expand: 'deliverables' })
            : screenPath('campaigns'),
          open_path: screenPath('campaigns'),
        };
      }
      const step = {
        id: String(row?.id || ''),
        name: String(row?.title || 'Step'),
        status: normalizeStatusValue(row?.status || 'not_started'),
        health: String(row?.health || 'not_started').toLowerCase(),
        current_start: row?.timeframe_start || null,
        current_due: row?.timeframe_due || null,
        owner_initials: String(row?.owner_initials || '--'),
        owner_name: String(row?.owner_name || ''),
        stage_name: String(row?.stage || ''),
        campaign_id: campaignId || null,
      };
      return {
        ...base,
        step,
        campaign: campaignId ? { id: campaignId } : undefined,
        deliverable: { title: String(row?.linked_deliverable_title || row?.deliverable_title || '-') },
        open_deep_link: campaignId
          ? campaignsPathWithTarget({ targetType: 'step', targetId: step.id, campaignId, expand: 'work' })
          : screenPath('campaigns'),
        open_path: screenPath('campaigns'),
      };
    }

    function stageKeyFromName(value) {
      return String(value || '').toLowerCase().trim().replace(/[\s-]+/g, '_');
    }

    function stageStepMatches(stage = {}, step = {}) {
      const stageId = String(stage?.id || '').trim();
      const stageDisplayId = String(stage?.display_id || '').trim();
      const stageNameKey = stageKeyFromName(stage?.name || '');
      const stepStageId = String(step?.stage_id || '').trim();
      const stepStageKey = stageKeyFromName(step?.stage_name || step?.stage || step?.deliverable_stage || '');
      return (
        (stageId && stepStageId === stageId)
        || (stageDisplayId && stepStageId === stageDisplayId)
        || (stageNameKey && stepStageKey && stepStageKey === stageNameKey)
      );
    }

    function stageStepsForWorkspaceStage(workspace = {}, stage = {}) {
      const steps = Array.isArray(workspace?.workflow_steps?.items) ? workspace.workflow_steps.items : [];
      return steps.filter(step => stageStepMatches(stage, step));
    }

    function normalizePanelChildItem(moduleType, source = {}, campaignId = '') {
      const type = String(moduleType || '').toLowerCase().trim();
      const id = String(source?.id || '').trim();
      if (!type || !id) return null;
      const status = normalizeStatusValue(source?.status || source?.step_state || 'not_started');
      const title = String(
        source?.title
        || source?.name
        || source?.client_name
        || source?.display_id
        || id
      ).trim();
      const displayTitle = type === 'stage'
        ? formatStageLabel(title || id, title || id || '-')
        : (title || id);
      return {
        module_type: type,
        id,
        campaign_id: String(campaignId || source?.campaign_id || '').trim(),
        title: displayTitle,
        status,
      };
    }

    function scopeChildrenItems(scope = {}) {
      const campaigns = Array.isArray(scope?.campaigns) ? scope.campaigns : [];
      return campaigns
        .map(campaign => normalizePanelChildItem('campaign', campaign, campaign?.id || campaign?.campaign_id || ''))
        .filter(Boolean);
    }

    function campaignChildrenItems(workspace = {}, campaignId = '') {
      const cid = String(campaignId || workspace?.campaign?.id || '').trim();
      const stages = Array.isArray(workspace?.stages) ? workspace.stages : [];
      const deliverables = Array.isArray(workspace?.deliverables?.items) ? workspace.deliverables.items : [];
      return [
        ...stages.map(stage => normalizePanelChildItem('stage', stage, cid)),
        ...deliverables.map(deliverable => normalizePanelChildItem('deliverable', deliverable, cid)),
      ].filter(Boolean);
    }

    function stageChildrenItems(workspace = {}, stage = {}, campaignId = '') {
      const cid = String(campaignId || workspace?.campaign?.id || '').trim();
      return stageStepsForWorkspaceStage(workspace, stage)
        .map(step => normalizePanelChildItem('step', step, cid))
        .filter(Boolean);
    }

    function deliverableChildrenItems(workspace = {}, deliverable = {}, campaignId = '') {
      const cid = String(campaignId || workspace?.campaign?.id || '').trim();
      const deliverableId = String(deliverable?.id || '').trim();
      const steps = Array.isArray(workspace?.workflow_steps?.items) ? workspace.workflow_steps.items : [];
      return steps
        .filter(step => String(step?.linked_deliverable_id || step?.deliverable_id || '').trim() === deliverableId)
        .map(step => normalizePanelChildItem('step', step, cid))
        .filter(Boolean);
    }

    function objectPanelChildrenItems(payload = {}) {
      if (Array.isArray(payload?.children_items)) return payload.children_items;
      const type = String(payload?.module_type || '').toLowerCase();
      if (type === 'scope' && payload?.scope) return scopeChildrenItems(payload.scope);
      return [];
    }

    function objectPanelChildrenTitleForType(moduleType = '') {
      const type = String(moduleType || '').toLowerCase().trim();
      if (type === 'campaign') return 'Campaigns';
      if (type === 'stage') return 'Stages';
      if (type === 'deliverable') return 'Deliverables';
      if (type === 'step') return 'Steps';
      if (type === 'scope') return 'Scopes';
      return 'Children';
    }

    function objectPanelChildrenSectionHtml(title, children = []) {
      const list = (Array.isArray(children) ? children : []).filter(Boolean);
      if (!list.length) return '';
      const rows = list.map(child => {
        const type = String(child?.module_type || '').toLowerCase();
        const id = String(child?.id || '').trim();
        const campaignId = String(child?.campaign_id || '').trim();
        const rawTitle = String(child?.title || id || '-').trim() || '-';
        const rowTitle = type === 'stage'
          ? formatStageLabel(rawTitle, rawTitle || '-')
          : rawTitle;
        const status = normalizeStatusValue(child?.status || 'not_started');
        if (!type || !id) return '';
        const dotClass = progressStatusClass(status);
        const doneClass = status === 'done' ? ' done' : '';
        return `
          <li class='object-panel-children-item'>
            <span class='object-panel-child-dot ${dotClass}' aria-hidden='true'></span>
            <button
              type='button'
              class='object-panel-child-link${doneClass}'
              data-object-panel-child-open='1'
              data-module-type='${type.replace(/'/g, '&#39;')}'
              data-object-id='${id.replace(/'/g, '&#39;')}'
              data-campaign-id='${campaignId.replace(/'/g, '&#39;')}'>${escapeHtml(rowTitle)}</button>
          </li>
        `;
      }).filter(Boolean).join('');
      if (!rows) return '';
      return `
        <div class='module-fields module-body object-panel-children-module'>
          <div class='object-panel-children-title'>${escapeHtml(String(title || 'Children'))}</div>
          <ul class='object-panel-children-list'>${rows}</ul>
        </div>
      `;
    }

    function objectPanelChildrenHtml(payload = {}) {
      const children = objectPanelChildrenItems(payload).filter(Boolean);
      if (!children.length) return '';
      const parentType = String(payload?.module_type || '').toLowerCase().trim();
      if (parentType === 'campaign') {
        const stages = children.filter(ch => String(ch?.module_type || '').toLowerCase() === 'stage');
        const deliverables = children.filter(ch => String(ch?.module_type || '').toLowerCase() === 'deliverable');
        return [
          objectPanelChildrenSectionHtml('Stages', stages),
          objectPanelChildrenSectionHtml('Deliverables', deliverables),
        ].filter(Boolean).join('');
      }
      const childType = String(children[0]?.module_type || '').toLowerCase();
      const title = objectPanelChildrenTitleForType(childType);
      return objectPanelChildrenSectionHtml(title, children);
    }

    async function fetchObjectPanelPayload(moduleType, objectId, campaignId = '') {
      const type = String(moduleType || '').toLowerCase().trim();
      const id = String(objectId || '').trim();
      const cid = String(campaignId || '').trim();
      if (!type || !id) return null;
      try {
        if (type === 'user') {
          const data = await api(`/api/users/${encodeURIComponent(id)}/panel`);
          if (!data) return null;
          return {
            module_type: 'user',
            user: data,
            campaign: null,
            children_items: [],
            open_label: 'Open',
            open_deep_link: screenPath('people'),
            open_path: screenPath('people'),
          };
        }
        if (type === 'scope') {
          const actorQ = currentActorId ? `?actor_user_id=${encodeURIComponent(currentActorId)}` : '';
          const data = await api(`/api/deals${actorQ}`);
          const scope = (data?.items || []).find(d => String(d?.id || '') === id);
          if (!scope) return null;
          return {
            module_type: 'scope',
            scope,
            children_items: scopeChildrenItems(scope),
            open_label: 'Open',
            open_deep_link: screenPath('deals'),
            open_path: screenPath('deals'),
          };
        }
        if (type === 'campaign') {
          const ws = await api(`/api/campaigns/${encodeURIComponent(id)}/workspace`);
          if (!ws?.campaign) return null;
          return {
            module_type: 'campaign',
            campaign: {
              ...(ws.campaign || {}),
              deliverables: [],
              work_steps: Array.isArray(ws?.workflow_steps?.items) ? ws.workflow_steps.items : [],
              stages: Array.isArray(ws?.stages) ? ws.stages : [],
              deliverables_summary: ws?.campaign?.deliverables_summary || { total: 0, not_started: 0, in_progress: 0, done: 0 },
              work_summary: ws?.campaign?.work_summary || { total: 0, not_started: 0, in_progress: 0, done: 0 },
            },
            children_items: campaignChildrenItems(ws, id),
            open_label: 'Open',
            open_deep_link: campaignsPathWithTarget({ targetType: 'campaign', targetId: id, campaignId: id }),
            open_path: screenPath('campaigns'),
          };
        }
        if (!cid) return null;
        const ws = await api(`/api/campaigns/${encodeURIComponent(cid)}/workspace`);
        if (!ws) return null;
        if (type === 'stage') {
          const stage = (ws?.stages || []).find(s => String(s?.id || '') === id);
          if (!stage) return null;
          const stageSteps = stageStepsForWorkspaceStage(ws, stage);
          return {
            module_type: 'stage',
            stage: {
              ...(stage || {}),
              campaign_id: cid,
              campaign_name: ws?.campaign?.title || '',
            },
            stage_steps: stageSteps,
            campaign: ws?.campaign || { id: cid },
            children_items: stageChildrenItems(ws, stage, cid),
            open_label: 'Open',
            open_deep_link: campaignsPathWithTarget({ targetType: 'stage', targetId: id, campaignId: cid, expand: 'work' }),
            open_path: screenPath('campaigns'),
          };
        }
        if (type === 'deliverable') {
          const deliverable = (ws?.deliverables?.items || []).find(d => String(d?.id || '') === id);
          if (!deliverable) return null;
          return {
            module_type: 'deliverable',
            deliverable,
            campaign: ws?.campaign || { id: cid },
            children_items: deliverableChildrenItems(ws, deliverable, cid),
            open_label: 'Open',
            open_deep_link: campaignsPathWithTarget({ targetType: 'deliverable', targetId: id, campaignId: cid, expand: 'deliverables' }),
            open_path: screenPath('campaigns'),
          };
        }
        if (type === 'step') {
          const step = (ws?.workflow_steps?.items || []).find(s => String(s?.id || '') === id);
          if (!step) return null;
          const linkedDeliverable = (ws?.deliverables?.items || []).find(d => String(d?.id || '') === String(step?.linked_deliverable_id || step?.deliverable_id || ''));
          const stages = Array.isArray(ws?.stages) ? ws.stages : [];
          const stepStageId = String(step?.stage_id || '').trim();
          const stepStageNameKey = stageKeyFromName(step?.stage_name || step?.stage || '');
          const resolvedStage = stages.find(st => String(st?.id || '').trim() === stepStageId)
            || stages.find(st => stageKeyFromName(st?.name || '') === stepStageNameKey)
            || null;
          return {
            module_type: 'step',
            step,
            stage: resolvedStage
              ? {
                  id: resolvedStage.id,
                  display_id: resolvedStage.display_id,
                  name: resolvedStage.name,
                  campaign_id: cid,
                }
              : {
                  id: stepStageId || '',
                  display_id: '',
                  name: step?.stage_name || step?.stage || '',
                  campaign_id: cid,
                },
            deliverable: { title: linkedDeliverable?.title || step?.linked_deliverable_title || '-' },
            campaign: ws?.campaign || { id: cid },
            children_items: [],
            open_label: 'Open',
            open_deep_link: campaignsPathWithTarget({ targetType: 'step', targetId: id, campaignId: cid, expand: 'work' }),
            open_path: screenPath('campaigns'),
          };
        }
        return null;
      } catch (_) {
        return null;
      }
    }

    function statusSelectOptions(selected) {
      const current = normalizeStatusValue(selected || 'not_started');
      return GLOBAL_STATUS_OPTIONS.map(opt => {
        const isSel = opt.value === current ? 'selected' : '';
        return `<option value='${opt.value}' ${isSel}>${opt.label}</option>`;
      }).join('');
    }

    function globalStatusFromDeliverableStatus(deliveryStatus) {
      const raw = String(deliveryStatus || '').toLowerCase();
      if (raw === 'planned') return 'not_started';
      if (raw === 'complete') return 'done';
      if (!raw) return 'not_started';
      return 'in_progress';
    }

    function deliverableRawStatusFromGlobal(globalStatus) {
      const s = normalizeStatusValue(globalStatus || 'not_started');
      if (s === 'not_started') return 'planned';
      if (s === 'done') return 'complete';
      if (s === 'on_hold') return 'client_changes_requested';
      return 'in_progress';
    }

    function deliverableNextTransitions(deliveryStatus) {
      const s = String(deliveryStatus || '').toLowerCase();
      const transitions = {
        planned: ['in_progress'],
        in_progress: ['awaiting_internal_review'],
        awaiting_internal_review: ['internal_review_complete'],
        internal_review_complete: ['awaiting_client_review'],
        awaiting_client_review: ['client_changes_requested', 'approved'],
        client_changes_requested: ['in_progress'],
        approved: ['ready_to_publish'],
        ready_to_publish: ['scheduled_or_published'],
        scheduled_or_published: ['complete'],
        complete: [],
      };
      return transitions[s] || [];
    }

    function statusPillDropdown(options = {}) {
      const id = options.id || `pill_${Math.random().toString(36).slice(2, 8)}`;
      const current = normalizeStatusValue(options.current || 'not_started');
      const currentLabel = options.currentLabel || statusLabel(current);
      const disabled = options.disabled ? 'disabled' : '';
      const list = Array.isArray(options.options) ? options.options : GLOBAL_STATUS_OPTIONS;
      const currentRaw = String(options.currentRaw || '').trim();
      const items = list.map((opt, idx) => {
        const selected = normalizeStatusValue(opt.value) === current;
        const chip = statusChip(opt.label ? opt.value : opt.value);
        const selAttr = selected ? " aria-selected='true'" : " aria-selected='false'";
        const dataRaw = opt.raw ? ` data-raw='${String(opt.raw).replace(/'/g, '&#39;')}'` : '';
        return `<button type='button' class='pill-dropdown-option' role='option' data-dropdown-option='1' data-value='${opt.value}'${dataRaw}${selAttr} data-index='${idx}'>${chip}</button>`;
      }).join('');
      const currentRawAttr = currentRaw ? ` data-current-raw='${currentRaw.replace(/'/g, '&#39;')}'` : '';
      return `
        <div class='pill-dropdown ${options.className || ''}' data-dropdown-kind='status' data-dropdown-id='${id}' data-context='${options.context || ''}' data-object-type='${options.objectType || ''}' data-object-id='${options.objectId || ''}' data-current-status='${current}'${currentRawAttr}>
          <button type='button' class='pill-dropdown-trigger' data-dropdown-trigger='1' aria-haspopup='listbox' aria-expanded='false' aria-label='${options.ariaLabel || currentLabel}' ${disabled}>
            ${statusChipWithChevron(current)}
          </button>
          <div class='pill-dropdown-menu' role='listbox' tabindex='-1'>
            ${items}
          </div>
        </div>
      `;
    }

    function ownerChipWithChevron(initials, fullName = null, owner = true, options = {}) {
      const pill = userPill(initials || '--', owner, fullName || null, options);
      return pill
        .replace("class='", "class='has-dropdown-caret ")
        .replace('</span>', "<span class='pill-dropdown-caret-inline' aria-hidden='true'>▾</span></span>");
    }

    function ownerPillDropdown(options = {}) {
      const id = options.id || `owner_${Math.random().toString(36).slice(2, 8)}`;
      const users = Array.isArray(options.users) ? options.users : [];
      const currentUserId = String(options.currentUserId || '');
      const currentUser = users.find(u => String(u.id) === currentUserId) || null;
      const currentInitials = currentUser?.initials || initialsFromName(currentUser?.name || '');
      const currentName = currentUser?.name || null;
      const disabled = options.disabled ? 'disabled' : '';
      const rows = [{ id: '', name: 'Unassigned', initials: '--' }, ...users];
      const items = rows.map((u, idx) => {
        const val = String(u.id || '');
        const selected = val === currentUserId;
        const safeName = String(u.name || '').replace(/'/g, '&#39;');
        const selAttr = selected ? " aria-selected='true'" : " aria-selected='false'";
        const initials = u.initials || initialsFromName(u.name || '');
        const chip = userPill(initials || '--', false, u.name || null, { userId: val, roleKey: options.roleKey || '' });
        return `<button type='button' class='pill-dropdown-option owner-option' role='option' data-dropdown-option='1' data-value='${val}' data-name='${safeName}' data-initials='${initials || '--'}'${selAttr} data-index='${idx}'><span class='owner-option-main'>${chip}<span class='owner-option-name'>${u.name || 'Unassigned'}</span></span></button>`;
      }).join('');
      return `
        <div class='pill-dropdown ${options.className || ''}' data-dropdown-kind='owner' data-dropdown-id='${id}' data-context='${options.context || ''}' data-object-type='${options.objectType || ''}' data-object-id='${options.objectId || ''}' data-owner-hidden-id='${options.hiddenInputId || ''}' data-role-key='${options.roleKey || ''}'>
          <button type='button' class='pill-dropdown-trigger' data-dropdown-trigger='1' aria-haspopup='listbox' aria-expanded='false' aria-label='${options.ariaLabel || 'Owner'}' ${disabled}>
            ${ownerChipWithChevron(currentInitials, currentName, true, { userId: currentUserId, roleKey: options.roleKey || '' })}
          </button>
          <div class='pill-dropdown-menu' role='listbox' tabindex='-1'>
            ${items}
          </div>
        </div>
      `;
    }

    function readonlyStatusPillDropdown(value, objectType = 'module', objectId = '') {
      return statusChip(value || 'not_started');
    }

    function closeAllPillDropdowns(exceptEl = null) {
      const dropdowns = Array.from(document.querySelectorAll('.pill-dropdown.open'));
      for (const dd of dropdowns) {
        if (exceptEl && (dd === exceptEl || dd.contains(exceptEl))) continue;
        dd.classList.remove('open');
        const trigger = dd.querySelector('[data-dropdown-trigger]');
        if (trigger) trigger.setAttribute('aria-expanded', 'false');
      }
    }

    function positionPillDropdownMenu(dropdown) {
      if (!dropdown) return;
      const menu = dropdown.querySelector('.pill-dropdown-menu');
      const trigger = dropdown.querySelector('[data-dropdown-trigger]');
      if (!(menu instanceof HTMLElement) || !(trigger instanceof HTMLElement)) return;
      const margin = 12;
      const gap = 6;
      const vw = window.innerWidth || document.documentElement.clientWidth || 0;
      const vh = window.innerHeight || document.documentElement.clientHeight || 0;
      if (vw <= 0 || vh <= 0) return;

      // Reset before measuring so we can compute natural menu size.
      menu.style.position = 'fixed';
      menu.style.left = '0px';
      menu.style.top = '0px';
      menu.style.right = 'auto';
      menu.style.bottom = 'auto';
      menu.style.maxHeight = `${Math.max(160, vh - (margin * 2))}px`;
      menu.style.overflowY = 'auto';

      const triggerRect = trigger.getBoundingClientRect();
      const menuRect = menu.getBoundingClientRect();

      let left = triggerRect.left;
      if (left + menuRect.width > vw - margin) left = vw - margin - menuRect.width;
      if (left < margin) left = margin;

      let top = triggerRect.bottom + gap;
      if (top + menuRect.height > vh - margin) {
        const above = triggerRect.top - gap - menuRect.height;
        if (above >= margin) top = above;
        else top = Math.max(margin, vh - margin - menuRect.height);
      }
      if (top < margin) top = margin;

      menu.style.left = `${Math.round(left)}px`;
      menu.style.top = `${Math.round(top)}px`;
    }

    function keepPillDropdownsInViewport() {
      const openDropdowns = Array.from(document.querySelectorAll('.pill-dropdown.open'));
      for (const dd of openDropdowns) positionPillDropdownMenu(dd);
    }

    function openPillDropdown(dropdown) {
      if (!dropdown) return;
      closeAllPillDropdowns(dropdown);
      dropdown.classList.add('open');
      positionPillDropdownMenu(dropdown);
      requestAnimationFrame(() => positionPillDropdownMenu(dropdown));
      const trigger = dropdown.querySelector('[data-dropdown-trigger]');
      if (trigger) trigger.setAttribute('aria-expanded', 'true');
      const selected = dropdown.querySelector('[data-dropdown-option][aria-selected=\"true\"]');
      if (selected) selected.focus();
      else {
        const first = dropdown.querySelector('[data-dropdown-option]');
        if (first) first.focus();
      }
    }

    function setPillDropdownSaving(dropdown, saving) {
      if (!dropdown) return;
      const trigger = dropdown.querySelector('[data-dropdown-trigger]');
      if (!trigger) return;
      if (!trigger.dataset.originalHtml) trigger.dataset.originalHtml = trigger.innerHTML;
      trigger.disabled = !!saving;
      if (saving) {
        trigger.innerHTML = `<span class='tag review'>Saving… <span class='pill-dropdown-caret-inline'>▾</span></span>`;
      } else {
        trigger.innerHTML = trigger.dataset.originalHtml || trigger.innerHTML;
      }
    }

    function setPillDropdownValue(dropdown, value) {
      if (!dropdown) return;
      const normalized = normalizeStatusValue(value);
      dropdown.setAttribute('data-current-status', normalized);
      const trigger = dropdown.querySelector('[data-dropdown-trigger]');
      if (!trigger) return;
      trigger.innerHTML = statusChipWithChevron(normalized);
      trigger.dataset.originalHtml = trigger.innerHTML;
      const hidden = dropdown.parentElement?.querySelector("input[type='hidden'][data-status-hidden='1']");
      if (hidden) hidden.value = normalized;
      const options = Array.from(dropdown.querySelectorAll('[data-dropdown-option]'));
      for (const opt of options) {
        opt.setAttribute('aria-selected', normalizeStatusValue(opt.getAttribute('data-value')) === normalized ? 'true' : 'false');
      }
    }

    function setOwnerDropdownValue(dropdown, userId, initials, fullName) {
      if (!dropdown) return;
      const trigger = dropdown.querySelector('[data-dropdown-trigger]');
      if (!trigger) return;
      const roleKey = String(dropdown.getAttribute('data-role-key') || '').trim();
      trigger.innerHTML = ownerChipWithChevron(initials || '--', fullName || null, true, { userId, roleKey });
      trigger.dataset.originalHtml = trigger.innerHTML;
      const hiddenId = dropdown.getAttribute('data-owner-hidden-id') || '';
      if (hiddenId) {
        const hidden = document.getElementById(hiddenId);
        if (hidden) hidden.value = userId || '';
      }
      const options = Array.from(dropdown.querySelectorAll('[data-dropdown-option]'));
      for (const opt of options) {
        opt.setAttribute('aria-selected', String(opt.getAttribute('data-value') || '') === String(userId || '') ? 'true' : 'false');
      }
    }

    function applyPanelDropdownDraftSelection(option, dropdown) {
      if (!option || !dropdown) return;
      const kind = String(dropdown.getAttribute('data-dropdown-kind') || 'status').toLowerCase();
      if (kind === 'owner') {
        const value = String(option.getAttribute('data-value') || '');
        const initials = String(option.getAttribute('data-initials') || '--');
        const fullName = String(option.getAttribute('data-name') || '');
        setOwnerDropdownValue(dropdown, value, initials, fullName);
        closeAllPillDropdowns();
        return;
      }
      const value = String(option.getAttribute('data-value') || '');
      const raw = String(option.getAttribute('data-raw') || '').trim();
      setPillDropdownValue(dropdown, value);
      if (raw) dropdown.setAttribute('data-current-raw', raw);
      const hiddenDelivery = dropdown.parentElement?.querySelector("input[data-delivery-status='1']");
      if (hiddenDelivery && raw) hiddenDelivery.value = raw.toLowerCase();
      closeAllPillDropdowns();
    }

    function statusChipWithChevron(value) {
      const chip = statusChip(value);
      return chip
        .replace('class="', 'class="has-dropdown-caret ')
        .replace('</span>', "<span class='pill-dropdown-caret-inline' aria-hidden='true'>▾</span></span>");
    }

    function updateCollapsedModuleSummaryOverflow() {
      const moduleTypes = ['campaign', 'scope', 'deliverable', 'stage', 'step'];
      const slotOrder = ['status', 'health', 'timeframe_start', 'timeframe_end', 'owner', 'stage', 'demand_track', 'campaign_id'];
      const hideOrder = ['demand_track', 'campaign_id', 'stage', 'owner', 'timeframe_start', 'timeframe_end', 'health', 'status'];
      const measureNaturalWidth = (el) => {
        if (!(el instanceof HTMLElement)) return 0;
        const clone = el.cloneNode(true);
        if (!(clone instanceof HTMLElement)) return 0;
        clone.classList.remove('hidden');
        clone.style.position = 'absolute';
        clone.style.visibility = 'hidden';
        clone.style.pointerEvents = 'none';
        clone.style.left = '-99999px';
        clone.style.top = '-99999px';
        clone.style.width = 'max-content';
        clone.style.maxWidth = 'none';
        clone.style.minWidth = '0';
        clone.style.overflow = 'visible';
        clone.style.whiteSpace = 'nowrap';
        document.body.appendChild(clone);
        const width = clone.getBoundingClientRect().width;
        clone.remove();
        return Number.isFinite(width) ? width : 0;
      };
      const visibleCardsByType = (moduleType) =>
        Array.from(document.querySelectorAll(`.module-card[data-module='${moduleType}']:not([open])`))
          .filter((card) => card instanceof HTMLElement && card.offsetParent !== null);
      const slotElement = (summary, slotName) => {
        if (!(summary instanceof HTMLElement)) return null;
        return summary.querySelector(`[data-slot='${slotName}']`);
      };
      const slotHasContent = (el) => {
        if (!(el instanceof HTMLElement)) return false;
        return String(el.textContent || '').trim().length > 0;
      };
      const slotRequiredWidth = (el) => {
        if (!(el instanceof HTMLElement) || !slotHasContent(el)) return 0;
        if (el.classList.contains('summary-pill-slot')) {
          const chip = el.querySelector('.tag');
          if (chip instanceof HTMLElement) return measureNaturalWidth(chip) + 4;
        }
        return measureNaturalWidth(el) + 2;
      };
      for (const moduleType of moduleTypes) {
        const cards = visibleCardsByType(moduleType);
        if (!cards.length) continue;
        const summaries = cards
          .map((card) => card.querySelector('.module-summary-grid'))
          .filter((s) => s instanceof HTMLElement);
        if (!summaries.length) continue;
        for (const summary of summaries) {
          for (const el of Array.from(summary.querySelectorAll('[data-slot]'))) {
            if (el instanceof HTMLElement) el.classList.remove('hidden');
          }
          summary.style.removeProperty('grid-template-columns');
        }
        const presentSlots = slotOrder.filter((slotName) =>
          summaries.some((summary) => slotHasContent(slotElement(summary, slotName)))
        );
        const widthBySlot = {};
        for (const slotName of presentSlots) {
          widthBySlot[slotName] = Math.max(
            ...summaries.map((summary) => slotRequiredWidth(slotElement(summary, slotName)))
          );
        }
        const availableWidths = summaries
          .map((summary) => summary.getBoundingClientRect().width || summary.clientWidth || 0)
          .filter((n) => Number.isFinite(n) && n > 0);
        const available = availableWidths.length ? Math.min(...availableWidths) : 0;
        const gap = Number.parseFloat(getComputedStyle(summaries[0]).columnGap || '0') || 0;
        let visibleSlots = [...presentSlots];
        const isCampaign = moduleType === 'campaign';
        const fits = () => {
          if (!available) return true;
          const widths = visibleSlots.reduce((acc, slotName) => acc + (widthBySlot[slotName] || 0), 0);
          const gaps = Math.max(0, visibleSlots.length - 1) * gap;
          return (widths + gaps) <= (available + 1);
        };
        let guard = 0;
        while (!fits() && guard < 24) {
          guard += 1;
          const slotToHide = hideOrder.find((slotName) =>
            visibleSlots.includes(slotName) && !(isCampaign && slotName === 'campaign_id')
          );
          if (!slotToHide) break;
          visibleSlots = visibleSlots.filter((slotName) => slotName !== slotToHide);
        }
        if (isCampaign && presentSlots.includes('campaign_id') && !visibleSlots.includes('campaign_id')) {
          visibleSlots.push('campaign_id');
        }
        for (const summary of summaries) {
          const activeSlots = slotOrder.filter((slotName) => {
            const el = slotElement(summary, slotName);
            const shouldShow = visibleSlots.includes(slotName) && slotHasContent(el);
            if (el instanceof HTMLElement) el.classList.toggle('hidden', !shouldShow);
            return shouldShow;
          });
          if (!activeSlots.length) continue;
          const template = activeSlots.map((slotName) => {
            if (slotName === 'campaign_id' && isCampaign) return 'minmax(max-content, 1fr)';
            const width = Math.max(24, Math.ceil(widthBySlot[slotName] || 0));
            return `${width}px`;
          }).join(' ');
          summary.style.gridTemplateColumns = template;
        }
      }
    }

    function enforceModulePairLayout(root = document) {
      const scope = root && typeof root.querySelectorAll === 'function' ? root : document;
      const rows = Array.from(scope.querySelectorAll('.module-row'));
      const isLabel = (el) => {
        if (!(el instanceof HTMLElement)) return false;
        if (el.tagName !== 'SPAN') return false;
        return /\:\s*$/.test(String(el.textContent || '').trim());
      };
      for (const row of rows) {
        if (row.dataset.modulePairNormalized === '1') continue;
        if (row.style.display === 'block') {
          row.dataset.modulePairNormalized = '1';
          continue;
        }
        const children = Array.from(row.children);
        if (!children.length) {
          row.dataset.modulePairNormalized = '1';
          continue;
        }
        const labels = children.filter(isLabel);
        if (!labels.length) {
          row.dataset.modulePairNormalized = '1';
          continue;
        }
        const fragment = document.createDocumentFragment();
        for (let i = 0; i < children.length; i += 1) {
          const child = children[i];
          if (!isLabel(child)) {
            fragment.appendChild(child);
            continue;
          }
          const pair = document.createElement('span');
          pair.className = 'module-pair';
          pair.appendChild(child);
          const next = children[i + 1];
          if (next && !isLabel(next)) {
            pair.appendChild(next);
            i += 1;
          }
          fragment.appendChild(pair);
        }
        row.textContent = '';
        row.appendChild(fragment);
        row.dataset.modulePairNormalized = '1';
      }
    }

    function applyModuleLayoutRules(root = document) {
      enforceModulePairLayout(root);
      updateCollapsedModuleSummaryOverflow();
    }

    function effortAllocationsHtml(efforts) {
      const rows = Array.isArray(efforts) ? efforts : [];
      if (!rows.length) return "<span class='sub'>-</span>";
      return rows.map(e => {
        const role = String(e.role || '').toUpperCase();
        const hours = Number(e.hours || 0).toFixed(2).replace(/\.00$/, '');
        const txt = `${role} ${hours}h`;
        return `<span class='tag review'>${txt}</span>`;
      }).join(' ');
    }

    async function loadCampaignHealthIndex() {
      const data = await api('/api/campaigns/health?limit=500&offset=0');
      const index = {};
      for (const item of (data.items || [])) {
        index[item.campaign_id] = item;
      }
      campaignHealthByCampaignId = index;
      return index;
    }

    function healthForCampaign(campaignDisplayId) {
      return campaignHealthByCampaignId[campaignDisplayId] || null;
    }

    function labelRole(role) {
      const map = {
        am: 'AM',
        head_ops: 'Head Ops',
        cm: 'CM',
        cc: 'CC',
        ccs: 'CCS',
        admin: 'Admin',
        leadership_viewer: 'Leadership',
        head_sales: 'Head Sales',
        client: 'Client',
      };
      return map[role] || role;
    }

    function labelRoleFlag(key) {
      const map = {
        show_deals_pipeline: 'Scopes Screen',
        show_capacity: 'Capacity Screen',
        show_risks: 'Risks Screen',
        show_reviews: 'Reviews Screen',
        show_admin: 'Admin Screen',
      };
      return map[key] || key;
    }

    function labelControl(controlId) {
      const map = {
        create_deal: 'Create Scope',
        create_submit_deal: 'Create+Submit Scope',
        create_demo_deal: 'Create Demo Scope',
        submit_latest_deal: 'Submit Latest Scope',
        ops_approve_latest_deal: 'Ops Approve Scope',
        generate_latest_campaigns: 'Generate Campaigns',
        complete_next_step: 'Complete Next Step',
        override_step_due: 'Override Step Due',
        run_ops_job: 'Run Ops Job',
        mark_ready_publish: 'Mark Ready Publish',
        run_sow_change: 'Run SOW Change',
        request_override: 'Request Capacity Override',
        approve_override: 'Approve Capacity Override',
        refresh_data: 'Refresh Data',
        advance_deliverable: 'Advance Deliverable',
        create_manual_risk: 'Create Manual Risk',
        resolve_manual_risk: 'Resolve Manual Risk',
        resolve_escalation: 'Resolve Escalation',
        manage_step: 'Manage Step',
        manage_deliverable_owner: 'Edit Deliverable Owner',
        manage_step_dates: 'Edit Step Dates',
        manage_deliverable_dates: 'Edit Deliverable Dates',
        edit_deliverable_stage: 'Edit Deliverable Stage',
        manage_campaign_assignments: 'Manage Campaign Assignments',
        manage_campaign_status: 'Manage Campaign Status',
        manage_campaign_dates: 'Edit Campaign Dates',
        admin_add_user: 'Add Users',
        admin_edit_user_name: 'Change User Names',
        admin_edit_user_email: 'Change User Emails',
        admin_set_user_team: 'Set User Team',
        admin_set_user_seniority_manager: 'Set Seniority (Manager/Standard)',
        admin_set_user_seniority_leadership: 'Set Seniority (Leadership)',
        admin_set_user_app_role_admin: 'Set App Role (Admin)',
        admin_set_user_app_role_superadmin: 'Set App Role (Superadmin)',
        admin_remove_user: 'Remove Users',
      };
      return map[controlId] || controlId;
    }

    function niceDate(value) {
      if (!value) return '-';
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return value;
      return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
    }

    function waitingLabel(deliverable) {
      if (deliverable.awaiting_client_review_since) {
        return `Client since ${niceDate(deliverable.awaiting_client_review_since)}`;
      }
      if (deliverable.awaiting_internal_review_since) {
        return `Internal since ${niceDate(deliverable.awaiting_internal_review_since)}`;
      }
      return '-';
    }

    function roleKeyToActorId(usersMap, role) {
      if (role === 'am') return usersMap.am;
      if (role === 'head_ops') return usersMap.ops;
      if (role === 'cm') return usersMap.cm;
      return usersMap.cc;
    }

    function effectiveRoleForUser(user) {
      const roles = Array.isArray(user?.roles) ? user.roles.map(r => String(r || '').toLowerCase()) : [];
      const priority = ['head_ops', 'admin', 'cm', 'cc', 'am', 'head_sales', 'dn', 'mm', 'leadership_viewer', 'client'];
      for (const role of priority) {
        if (roles.includes(role)) return role;
      }
      const team = String(user?.primary_team || '').toLowerCase();
      if (team === 'sales') return 'am';
      if (team === 'editorial') return 'cc';
      if (team === 'marketing') return 'mm';
      if (team === 'client_services') return 'cm';
      return 'cm';
    }

    function defaultScreenForRole(role) {
      if (role === 'cm' || role === 'cc') return 'my-work';
      return 'home';
    }

    function isSalesLeadership() {
      return String(currentActorIdentity?.team || '').toLowerCase() === 'sales'
        && String(currentActorIdentity?.seniority || '').toLowerCase() === 'leadership';
    }

    function isClientServicesLeadership() {
      return String(currentActorIdentity?.team || '').toLowerCase() === 'client_services'
        && String(currentActorIdentity?.seniority || '').toLowerCase() === 'leadership';
    }

    function canApproveScopes() {
      return canUseControl('ops_approve_latest_deal', currentRole) || isSalesLeadership() || isClientServicesLeadership();
    }

    function canGenerateScopeCampaigns() {
      return canUseControl('generate_latest_campaigns', currentRole) || isClientServicesLeadership();
    }

    function screenPath(screen) {
      const map = {
        home: '/home',
        'my-work': '/my-work',
        deals: '/scopes',
        people: '/people',
        campaigns: '/campaigns',
        gantt: '/gantt',
        reviews: '/reviews',
        risks: '/risks',
        capacity: '/capacity',
        admin: '/admin',
      };
      return map[screen] || '/home';
    }

    function reviewsPathWithDeliverable(deliverableId) {
      const base = screenPath('reviews');
      if (!deliverableId) return base;
      return `${base}?deliverable=${encodeURIComponent(deliverableId)}`;
    }

    function campaignsPathWithTarget(target = {}) {
      const qs = new URLSearchParams();
      if (target.targetType) qs.set('targetType', String(target.targetType).toLowerCase());
      if (target.targetId) qs.set('targetId', String(target.targetId));
      if (target.campaignId) qs.set('campaignId', String(target.campaignId));
      if (target.expand) qs.set('expand', String(target.expand).toLowerCase());
      const query = qs.toString();
      return query ? `${screenPath('campaigns')}?${query}` : screenPath('campaigns');
    }

    function popoverOpenDeepLinkForPayload(payload = {}) {
      const moduleType = String(payload.module_type || '').toLowerCase();
      if (moduleType === 'campaign') {
        const campaignId = payload?.campaign?.id || null;
        return campaignId
          ? campaignsPathWithTarget({ targetType: 'campaign', targetId: campaignId, campaignId })
          : screenPath('campaigns');
      }
      if (moduleType === 'milestone') {
        const campaignId = payload?.campaign_id || payload?.campaign?.id || null;
        return campaignId
          ? campaignsPathWithTarget({ targetType: 'campaign', targetId: campaignId, campaignId })
          : screenPath('campaigns');
      }
      if (moduleType === 'stage') {
        const stageId = payload?.stage?.id || null;
        const campaignId = payload?.stage?.campaign_id || payload?.campaign?.id || null;
        if (stageId && campaignId) {
          return campaignsPathWithTarget({ targetType: 'stage', targetId: stageId, campaignId, expand: 'work' });
        }
        return campaignId
          ? campaignsPathWithTarget({ targetType: 'campaign', targetId: campaignId, campaignId })
          : screenPath('campaigns');
      }
      if (moduleType === 'deliverable') {
        const deliverableId = payload?.deliverable?.id || null;
        const campaignId = payload?.deliverable?.campaign_id || payload?.campaign?.id || null;
        if (deliverableId && campaignId) {
          return campaignsPathWithTarget({ targetType: 'deliverable', targetId: deliverableId, campaignId, expand: 'deliverables' });
        }
        return campaignId
          ? campaignsPathWithTarget({ targetType: 'campaign', targetId: campaignId, campaignId })
          : screenPath('campaigns');
      }
      if (moduleType === 'step') {
        const stepId = payload?.step?.id || null;
        const campaignId = payload?.step?.campaign_id || payload?.campaign?.id || null;
        if (stepId && campaignId) {
          return campaignsPathWithTarget({ targetType: 'step', targetId: stepId, campaignId, expand: 'work' });
        }
        return campaignId
          ? campaignsPathWithTarget({ targetType: 'campaign', targetId: campaignId, campaignId })
          : screenPath('campaigns');
      }
      return payload?.open_path || screenPath('campaigns');
    }

    function screenFromPath(path) {
      if (path === '/my-work') return 'my-work';
      if (path === '/deals' || path === '/scopes') return 'deals';
      if (path === '/people') return 'people';
      if (path === '/campaigns' || path.startsWith('/campaigns/')) return 'campaigns';
      if (path === '/gantt') return 'gantt';
      if (path === '/reviews') return 'reviews';
      if (path === '/risks') return 'risks';
      if (path === '/capacity') return 'capacity';
      if (path === '/admin') return 'admin';
      return 'home';
    }

    function campaignIdFromPath(path) {
      if (!path.startsWith('/campaigns/')) return null;
      const parts = path.split('/').filter(Boolean);
      return parts.length >= 2 ? decodeURIComponent(parts[1]) : null;
    }

    function canViewScreen(screen) {
      const flags = currentRoleFlags || {};
      if (screen === 'home' || screen === 'my-work' || screen === 'people' || screen === 'campaigns' || screen === 'gantt') return true;
      if (screen === 'deals') return flags.show_deals_pipeline !== false;
      if (screen === 'reviews') return !!flags.show_reviews;
      if (screen === 'risks') return !!flags.show_risks;
      if (screen === 'capacity') return !!flags.show_capacity;
      if (screen === 'admin') return !!flags.show_admin;
      return false;
    }

    function renderNavActive() {
      const nav = document.getElementById('appNav');
      if (!nav) return;
      nav.querySelectorAll('button').forEach(btn => {
        const target = btn.getAttribute('data-screen') || '';
        const visible = canViewScreen(target);
        btn.classList.toggle('hidden', !visible);
        btn.setAttribute('aria-hidden', visible ? 'false' : 'true');
        btn.classList.toggle('active', target === currentScreen);
      });
    }

    function applyScreenLayoutMode() {
      const screens = ['home', 'my-work', 'deals', 'people', 'campaigns', 'gantt', 'reviews', 'risks', 'capacity', 'admin'];
      screens.forEach(screen => {
        document.body.classList.toggle(`screen-${screen}`, currentScreen === screen);
      });
    }

    function syncRailAnchors() {
      const root = document.documentElement;
      const header = document.querySelector('header');
      const footer = document.querySelector('.app-footer');
      const headerHeight = header ? Math.ceil(header.getBoundingClientRect().height) : 72;
      const footerHeight = footer ? Math.ceil(footer.getBoundingClientRect().height) : 0;
      root.style.setProperty('--header-offset', `${headerHeight}px`);
      root.style.setProperty('--footer-offset', `${footerHeight}px`);
    }

    function demoRailStorageKey() {
      return `demoRailMinimised:${currentRole || 'unknown'}`;
    }

    function toggleDemoRail() {
      demoRailMinimised = !demoRailMinimised;
      try {
        localStorage.setItem(demoRailStorageKey(), demoRailMinimised ? '1' : '0');
      } catch (_) {}
      applyControlVisibility();
    }

    async function navigateScreen(screen) {
      closeItemPopover();
      closeCapacityPopover();
      window.location.href = screenPath(screen);
    }

    function queueTitle(label, count) {
      return `<div class='queue-title'><span>${label}</span><span class='tag done'>${count}</span></div>`;
    }

    function userName(userId) {
      if (!userId) return '-';
      return usersById[userId]?.name || userId;
    }

    function initialsFromName(name) {
      const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
      if (!parts.length) return '--';
      if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
      return `${parts[0][0] || ''}${parts[parts.length - 1][0] || ''}`.toUpperCase();
    }

    function normalizeIdentityKey(value) {
      return String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');
    }

    function normalizePillTeam(team) {
      const key = String(team || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
      if (key === 'client_services' || key === 'campaign_manager' || key === 'campaign_managers') return 'client_services';
      if (key === 'sales' || key === 'account_manager' || key === 'account_managers') return 'sales';
      if (key === 'editorial' || key === 'content_creator' || key === 'content_creators') return 'editorial';
      return '';
    }

    function pillTeamFromRole(roleKey) {
      const key = String(roleKey || '').trim().toLowerCase();
      if (key === 'cm' || key === 'head_ops') return 'client_services';
      if (key === 'am' || key === 'head_sales') return 'sales';
      if (key === 'cc' || key === 'ccs') return 'editorial';
      return '';
    }

    function resolvePillTeam(options = {}) {
      const explicitTeam = normalizePillTeam(options?.team);
      if (explicitTeam) return explicitTeam;
      const roleTeam = pillTeamFromRole(options?.roleKey);
      if (roleTeam) return roleTeam;
      const userId = String(options?.userId || '').trim();
      if (userId) {
        const userById = usersById[userId];
        const teamById = normalizePillTeam(userById?.primary_team || '');
        if (teamById) return teamById;
      }
      const nameKey = normalizeIdentityKey(options?.fullName || '');
      if (nameKey) {
        const userByName = usersByName[nameKey];
        const teamByName = normalizePillTeam(userByName?.primary_team || '');
        if (teamByName) return teamByName;
      }
      return 'client_services';
    }

    function stepStateFromItem(item) {
      const explicit = item?.step?.status || item?.step?.step_state;
      if (explicit) return normalizeStatusValue(explicit);
      if (item?.step?.waiting_on_type) return `blocked_${item.step.waiting_on_type}`;
      if (normalizeStatusValue(item?.deliverable?.status) === 'done') return 'done';
      return 'in_progress';
    }

    function userPill(initials, owner = false, fullName = null, options = {}) {
      const label = String(fullName || '').trim();
      const team = resolvePillTeam({
        team: options?.team,
        roleKey: options?.roleKey,
        userId: options?.userId,
        fullName: label,
      });
      const teamClass = team ? `team-${team}` : 'team-client-services';
      const cls = owner ? `user-pill ${teamClass} owner` : `user-pill ${teamClass}`;
      const safeLabel = label ? label.replace(/"/g, '&quot;') : '';
      const tooltipAttr = safeLabel ? ` title="${safeLabel}" aria-label="${safeLabel}"` : '';
      return `<span class='${cls}'${tooltipAttr}>${initials || '--'}</span>`;
    }

    function panelDetailValueText(value, fallback = '-') {
      const text = String(value ?? '').trim();
      return text || fallback;
    }

    function panelTimeframeText(startIso, endIso) {
      const start = startIso ? niceDate(startIso) : '-';
      const end = endIso ? niceDate(endIso) : '-';
      return `${start} → ${end}`;
    }

    function panelPercentText(value) {
      const n = Number(value);
      const pct = Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : 0;
      return `${pct}%`;
    }

    function panelDetailLink(label, moduleType, objectId, campaignId = '') {
      const text = panelDetailValueText(label, '-');
      const type = String(moduleType || '').toLowerCase().trim();
      const id = String(objectId || '').trim();
      if (!type || !id) return `<span>${escapeHtml(text)}</span>`;
      const cid = String(campaignId || '').trim().replace(/'/g, '&#39;');
      return `<button type='button' class='panel-details-link' onclick="openObjectPanelChild('${type}', '${id.replace(/'/g, '&#39;')}', '${cid}')">${escapeHtml(text)}</button>`;
    }

    function panelDetailsSection(rows = []) {
      const safeRows = (Array.isArray(rows) ? rows : [])
        .filter(row => String(row?.label || '').trim() && String(row?.valueHtml || '').trim());
      if (!safeRows.length) return '';
      return `
        <div class='panel-details-title'>Details</div>
        <div class='panel-details-grid'>
          ${safeRows.map(row => `
            <div class='panel-details-row'>
              <div class='panel-details-label'>${escapeHtml(String(row.label || ''))}</div>
              <div class='panel-details-value'>${row.valueHtml}</div>
            </div>
          `).join('')}
        </div>
      `;
    }

    function userCapacityTagClass(utilizationPct) {
      const pct = Number(utilizationPct || 0);
      if (!Number.isFinite(pct) || pct <= 0) return 'neutral';
      if (pct > 100) return 'risk';
      if (pct >= 90) return 'review';
      return 'ok';
    }

    function userPanelDetailsModuleHtml(user = {}) {
      const teamText = `${escapeHtml(toTitle(String(user?.team || '-').replaceAll('_', ' ')))}${user?.editorial_subteam ? ` (${escapeHtml(String(user.editorial_subteam).toUpperCase())})` : ''}`;
      return `
        <div class='module-fields module-body object-panel-user-details-module'>
          <div class='panel-details-title'>Details</div>
          <div class='panel-details-grid'>
            <div class='panel-details-row'>
              <div class='panel-details-label'>Name</div>
              <div class='panel-details-value'><span>${escapeHtml(String(user?.name || '-'))}</span></div>
            </div>
            <div class='panel-details-row'>
              <div class='panel-details-label'>Team</div>
              <div class='panel-details-value'><span>${teamText}</span></div>
            </div>
          </div>
        </div>
      `;
    }

    function userPanelCampaignsModuleHtml(campaigns = []) {
      const safeCampaigns = (Array.isArray(campaigns) ? campaigns : []).filter(Boolean);
      const rows = safeCampaigns.map(c => {
        const campaignId = String(c?.id || '').trim();
        const title = String(c?.title || c?.id || '-').trim() || '-';
        const safeCampaignId = campaignId.replace(/'/g, '&#39;');
        if (!campaignId) {
          return `
            <li class='object-panel-children-item'>
              <span class='object-panel-child-dot' aria-hidden='true'></span>
              <span>${escapeHtml(title)}</span>
            </li>
          `;
        }
        return `
          <li class='object-panel-children-item'>
            <span class='object-panel-child-dot' aria-hidden='true'></span>
            <button
              type='button'
              class='object-panel-child-link'
              data-object-panel-child-open='1'
              data-module-type='campaign'
              data-object-id='${safeCampaignId}'
              data-campaign-id='${safeCampaignId}'
            >
              ${escapeHtml(title)}
            </button>
          </li>
        `;
      }).join('');
      return `
        <div class='module-fields module-body object-panel-user-campaigns-module'>
          <div class='panel-details-title'>Campaigns</div>
          ${rows
            ? `<ul class='object-panel-children-list'>${rows}</ul>`
            : "<div class='sub'>No campaigns assigned.</div>"}
        </div>
      `;
    }

    function userPanelCapacityModuleHtml(capacityRows = []) {
      const rows = (Array.isArray(capacityRows) ? capacityRows : []).slice(0, 6);
      const content = rows.map(r => {
        const weekStart = String(r?.week_start || '').trim();
        const forecast = Number(r?.forecast_planned_hours || 0);
        const capacity = Number(r?.capacity_hours || 0);
        const active = Number(r?.active_planned_hours || 0);
        const utilization = Number(r?.utilization_pct || 0);
        const pctLabel = Number.isFinite(utilization) ? `${Math.round(utilization)}%` : '0%';
        const tagClass = userCapacityTagClass(utilization);
        return `
          <div class='panel-details-row'>
            <div class='panel-details-label'>${escapeHtml(weekStart ? niceDate(weekStart) : '-')}</div>
            <div class='panel-details-value'>
              <span>${Number.isFinite(forecast) ? forecast.toFixed(1) : '0.0'} / ${Number.isFinite(capacity) ? capacity.toFixed(1) : '0.0'}h</span>
              <span class='tag ${tagClass}'>${escapeHtml(pctLabel)}</span>
              <span class='sub'>Active ${Number.isFinite(active) ? active.toFixed(1) : '0.0'}h</span>
            </div>
          </div>
        `;
      }).join('');
      return `
        <div class='module-fields module-body object-panel-user-capacity-module'>
          <div class='panel-details-title'>Capacity</div>
          ${content
            ? `<div class='panel-details-grid'>${content}</div>`
            : "<div class='sub'>No capacity rows available.</div>"}
        </div>
      `;
    }

    function roleShortLabel(roleKey) {
      const key = String(roleKey || '').toLowerCase().trim();
      if (key === 'ccs') return 'CC Support';
      if (key === 'head_ops') return 'Head Ops';
      if (!key) return '-';
      return key.toUpperCase();
    }

    function hoursLabel(hours) {
      const n = Number(hours);
      const safe = Number.isFinite(n) ? Math.max(0, n) : 0;
      const txt = safe.toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');
      return `${txt} hr`;
    }

    function roleHoursLabel(roleKey, hours) {
      return `${roleShortLabel(roleKey)} - ${hoursLabel(hours)}`;
    }

    function campaignAssignmentsByRoleForPanel(payload = {}) {
      const assigned = Array.isArray(payload?.campaign?.assigned_users) ? payload.campaign.assigned_users : [];
      const byRole = {};
      for (const a of assigned) {
        const role = String(a?.role || '').toLowerCase().trim();
        if (!role) continue;
        byRole[role] = a;
      }
      return byRole;
    }

    function panelTeamUserByRole(roleKey, byRole = {}, preferredUserId = '') {
      const normalizedRole = String(roleKey || '').toLowerCase().trim();
      const preferredId = String(preferredUserId || '').trim();
      if (preferredId) {
        const preferredName = userName(preferredId);
        return {
          assigned: !!preferredName && preferredName !== '-',
          userId: preferredId,
          name: panelDetailValueText(preferredName, '-'),
          initials: initialsFromName(preferredName || ''),
          roleKey: normalizedRole,
        };
      }
      const entry = byRole[normalizedRole] || null;
      const userId = String(entry?.user_id || '').trim();
      const name = panelDetailValueText(entry?.name || (userId ? userName(userId) : ''), '-');
      const initials = String(entry?.initials || initialsFromName(name || '') || '--').trim() || '--';
      return {
        assigned: !!entry?.user_id,
        userId: userId || '',
        name,
        initials,
        roleKey: normalizedRole,
      };
    }

    function panelTeamUserHtml(user = {}) {
      if (!user?.assigned) return "<span class='tag warn'>Unassigned</span>";
      const isOwner = !!user?.isOwner;
      const name = panelDetailValueText(user?.name, '-');
      const userId = String(user?.userId || '').trim();
      const nameHtml = userId
        ? `<button type='button' class='panel-details-link' onclick="openObjectPanelChild('user', '${userId.replace(/'/g, '&#39;')}', '')">${escapeHtml(name)}</button>`
        : `<span>${escapeHtml(name)}</span>`;
      return `${userPill(user?.initials || '--', isOwner, user?.name || null, { userId: userId, roleKey: user?.roleKey || '' })}${nameHtml}`;
    }

    function panelTeamRoleEditorHtml(options = {}) {
      const roleKey = String(options?.roleKey || '').toLowerCase().trim();
      const dropdownId = String(options?.dropdownId || '').trim();
      const hiddenId = String(options?.hiddenId || '').trim();
      const campaignId = String(options?.campaignId || '').trim();
      const currentUserId = String(options?.currentUserId || '').trim();
      if (!roleKey || !dropdownId || !hiddenId || !campaignId) {
        return panelTeamUserHtml({
          assigned: !!currentUserId,
          name: options?.currentName || '-',
          initials: options?.currentInitials || '--',
        });
      }
      const users = usersForAssignmentSlot(roleKey)
        .map(u => ({ id: u.id, name: u.name, initials: (u.initials || initialsFromName(u.name || '')) }));
      return `
        <input type='hidden' id='${hiddenId}' data-campaign-assign-hidden='1' data-role-key='${roleKey}' value='${currentUserId}' />
        ${ownerPillDropdown({
          id: dropdownId,
          currentUserId,
          users,
          objectType: 'campaign_assignment',
          objectId: campaignId,
          context: 'panel',
          hiddenInputId: hiddenId,
          roleKey,
          ariaLabel: `${roleShortLabel(roleKey)} assignment`,
        })}
      `;
    }

    function usersForRoleEditor(roleKey = '') {
      const role = String(roleKey || '').toLowerCase().trim();
      const teamScoped = usersForAssignmentSlot(role);
      if (Array.isArray(teamScoped) && teamScoped.length) return teamScoped;
      return Array.isArray(usersDirectory) ? usersDirectory : [];
    }

    function objectPanelTeamSectionHtml(rows = []) {
      const safeRows = (Array.isArray(rows) ? rows : [])
        .filter(row => String(row?.label || '').trim() && String(row?.valueHtml || '').trim());
      if (!safeRows.length) return '';
      return `
        <div class='module-fields module-body object-panel-team-module'>
          <div class='panel-details-title'>Team</div>
          <div class='panel-details-grid'>
            ${safeRows.map(row => `
              <div class='panel-details-row'>
                <div class='panel-details-label'>${escapeHtml(String(row.label || ''))}</div>
                <div class='panel-details-value'>${row.valueHtml}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    function stageHoursByRole(payload = {}) {
      const steps = Array.isArray(payload?.stage_steps)
        ? payload.stage_steps
        : (Array.isArray(payload?.stage?.steps) ? payload.stage.steps : []);
      const totals = {};
      for (const step of steps) {
        const allocations = Array.isArray(step?.effort_allocations) ? step.effort_allocations : [];
        for (const effort of allocations) {
          const role = String(effort?.role || '').toLowerCase().trim();
          if (!role) continue;
          const hours = Number(effort?.hours || 0);
          if (!Number.isFinite(hours)) continue;
          totals[role] = Number(totals[role] || 0) + hours;
        }
      }
      return totals;
    }

    function stageRoleKeys(payload = {}) {
      const steps = Array.isArray(payload?.stage_steps)
        ? payload.stage_steps
        : (Array.isArray(payload?.stage?.steps) ? payload.stage.steps : []);
      const hoursByRole = stageHoursByRole(payload);
      const knownOrder = ['cc', 'ccs', 'cm', 'am', 'head_ops', 'head_sales', 'dn', 'mm', 'admin', 'client', 'leadership_viewer'];
      const knownOrderIndex = Object.fromEntries(knownOrder.map((role, idx) => [role, idx]));
      const inferred = new Set();

      for (const step of steps) {
        const ownerRole = String(step?.owner_role || '').toLowerCase().trim();
        if (ownerRole) inferred.add(ownerRole);
      }
      for (const role of Object.keys(hoursByRole)) {
        const key = String(role || '').toLowerCase().trim();
        if (key) inferred.add(key);
      }

      return Array.from(inferred).sort((a, b) => {
        const ai = Object.prototype.hasOwnProperty.call(knownOrderIndex, a) ? knownOrderIndex[a] : Number.MAX_SAFE_INTEGER;
        const bi = Object.prototype.hasOwnProperty.call(knownOrderIndex, b) ? knownOrderIndex[b] : Number.MAX_SAFE_INTEGER;
        if (ai !== bi) return ai - bi;
        return a.localeCompare(b);
      });
    }

    function stepHoursByRole(step = {}) {
      const totals = {};
      const allocations = Array.isArray(step?.effort_allocations) ? step.effort_allocations : [];
      for (const effort of allocations) {
        const role = String(effort?.role || '').toLowerCase().trim();
        if (!role) continue;
        const hours = Number(effort?.hours || 0);
        if (!Number.isFinite(hours)) continue;
        totals[role] = Number(totals[role] || 0) + hours;
      }
      return totals;
    }

    function stepRoleUserFromEfforts(step = {}, roleKey = '') {
      const role = String(roleKey || '').toLowerCase().trim();
      if (!role) return '';
      const allocations = Array.isArray(step?.effort_allocations) ? step.effort_allocations : [];
      const match = allocations.find(e => String(e?.role || '').toLowerCase().trim() === role && String(e?.assigned_user_id || '').trim());
      return String(match?.assigned_user_id || '').trim();
    }

    function objectPanelTeamRows(payload = {}) {
      const type = String(payload?.module_type || '').toLowerCase().trim();
      const byRole = campaignAssignmentsByRoleForPanel(payload);
      const objectId = String(
        type === 'step'
          ? (payload?.step?.id || payload?.step?.display_id || '')
          : type === 'stage'
            ? (payload?.stage?.id || payload?.stage?.display_id || '')
            : type === 'campaign'
              ? (payload?.campaign?.id || payload?.campaign?.campaign_id || '')
              : (payload?.scope?.id || payload?.scope?.display_id || '')
      ).trim();
      const campaignId = String(
        payload?.campaign?.id
        || payload?.campaign?.campaign_id
        || payload?.stage?.campaign_id
        || payload?.step?.campaign_id
        || ''
      ).trim();
      const editMode = !!(objectId && isModuleEditing(type, objectId));
      const canEditRoleAssignments = (type === 'campaign' || type === 'stage')
        && editMode
        && canUseControl('manage_campaign_assignments', currentRole)
        && !!campaignId;
      if (type === 'scope') {
        const am = payload?.scope?.am_user || {};
        const amName = panelDetailValueText(am?.name || payload?.scope?.am_name || '', '-');
        const amInitials = String(am?.initials || payload?.scope?.am_initials || initialsFromName(amName || '') || '--').trim() || '--';
        const amUserId = String(am?.user_id || payload?.scope?.am_user_id || '').trim();
        const assigned = !!amUserId || amName !== '-';
        const canEditScopeAm = editMode
          && (
            canUseControl('create_deal', currentRole)
            || canUseControl('ops_approve_latest_deal', currentRole)
            || canUseControl('manage_campaign_assignments', currentRole)
          );
        const hiddenId = `panelTeamAssign_scope_${objectId || 'scope'}_am`;
        const valueHtml = canEditScopeAm
          ? `
            <input type='hidden' id='${hiddenId}' data-scope-assign-hidden='1' data-role-key='am' value='${amUserId}' />
            ${ownerPillDropdown({
              id: `panelTeamAssignDrop_scope_${objectId || 'scope'}_am`,
              currentUserId: amUserId,
              users: usersForAssignmentSlot('am').map(u => ({ id: u.id, name: u.name, initials: (u.initials || initialsFromName(u.name || '')) })),
              objectType: 'scope_assignment',
              objectId: objectId || 'scope',
              context: 'panel',
              hiddenInputId: hiddenId,
              roleKey: 'am',
              ariaLabel: 'Scope AM assignment',
            })}
          `
          : panelTeamUserHtml({ assigned, name: amName, initials: amInitials, userId: amUserId, roleKey: 'am', isOwner: true });
        return [
          {
            label: 'AM',
            valueHtml,
          },
        ];
      }
      if (type === 'campaign') {
        const roleOrder = ['cc', 'ccs', 'cm', 'am'];
        return roleOrder
          .filter(role => canEditRoleAssignments || role !== 'ccs' || !!byRole.ccs?.user_id)
          .map(role => {
            const user = panelTeamUserByRole(role, byRole);
            const valueHtml = canEditRoleAssignments
              ? panelTeamRoleEditorHtml({
                  roleKey: role,
                  campaignId,
                  currentUserId: user?.userId || '',
                  currentName: user?.name || '-',
                  currentInitials: user?.initials || '--',
                  hiddenId: `panelTeamAssign_${type}_${objectId || campaignId}_${role}`,
                  dropdownId: `panelTeamAssignDrop_${type}_${objectId || campaignId}_${role}`,
                })
              : panelTeamUserHtml(user);
            return {
              label: roleShortLabel(role),
              valueHtml,
            };
          });
      }
      if (type === 'stage') {
        const roleOrder = stageRoleKeys(payload);
        const hours = stageHoursByRole(payload);
        return roleOrder
          .filter(role => String(role || '').trim())
          .map(role => {
            const user = panelTeamUserByRole(role, byRole);
            const valueHtml = canEditRoleAssignments
              ? panelTeamRoleEditorHtml({
                  roleKey: role,
                  campaignId,
                  currentUserId: user?.userId || '',
                  currentName: user?.name || '-',
                  currentInitials: user?.initials || '--',
                  hiddenId: `panelTeamAssign_${type}_${objectId || campaignId}_${role}`,
                  dropdownId: `panelTeamAssignDrop_${type}_${objectId || campaignId}_${role}`,
                })
              : panelTeamUserHtml(user);
            return {
              label: roleHoursLabel(role, hours[role] || 0),
              valueHtml,
            };
          });
      }
      if (type === 'step') {
        const step = payload?.step || {};
        const ownerRole = String(step?.owner_role || '').toLowerCase().trim();
        const hoursByRole = stepHoursByRole(step);
        const stepId = String(step?.id || objectId || '').trim();
        const canEditStepOwner = editMode && canUseControl('manage_step', currentRole) && !!stepId;
        const canEditStepRoleAssignments = editMode
          && (canUseControl('manage_campaign_assignments', currentRole) || canUseControl('manage_step', currentRole))
          && !!campaignId;
        const ownerUser = panelTeamUserByRole(
          ownerRole,
          byRole,
          String(step?.next_owner_user_id || '').trim(),
        );
        const ownerUsers = usersForRoleEditor(ownerRole)
          .map(u => ({ id: u.id, name: u.name, initials: (u.initials || initialsFromName(u.name || '')) }));
        const ownerHiddenId = `panelStepOwner_${stepId || 'step'}`;
        const ownerValueHtml = canEditStepOwner
          ? `
            <input type='hidden' id='${ownerHiddenId}' data-owner-hidden='1' value='${ownerUser?.userId || ''}' />
            ${ownerPillDropdown({
              id: `panelTeamStepOwnerDrop_${stepId || 'step'}`,
              currentUserId: ownerUser?.userId || '',
              users: ownerUsers,
              objectType: 'step',
              objectId: stepId,
              context: 'panel',
              hiddenInputId: ownerHiddenId,
              roleKey: ownerRole || '',
              ariaLabel: 'Step owner assignment',
            })}
          `
          : panelTeamUserHtml({ ...ownerUser, isOwner: true });
        const rows = [{
          label: roleHoursLabel(ownerRole || 'owner', hoursByRole[ownerRole] || 0),
          valueHtml: ownerValueHtml,
        }];
        const extraRoles = Object.keys(hoursByRole)
          .filter(role => role && role !== ownerRole && Number(hoursByRole[role] || 0) > 0)
          .sort();
        for (const role of extraRoles) {
          const preferredUserId = stepRoleUserFromEfforts(step, role);
          const user = panelTeamUserByRole(role, byRole, preferredUserId);
          const valueHtml = canEditStepRoleAssignments
            ? panelTeamRoleEditorHtml({
                roleKey: role,
                campaignId,
                currentUserId: user?.userId || '',
                currentName: user?.name || '-',
                currentInitials: user?.initials || '--',
                hiddenId: `panelTeamAssign_${type}_${stepId || campaignId}_${role}`,
                dropdownId: `panelTeamAssignDrop_${type}_${stepId || campaignId}_${role}`,
              })
            : panelTeamUserHtml({ ...user, isOwner: false });
          rows.push({
            label: roleHoursLabel(role, hoursByRole[role] || 0),
            valueHtml,
          });
        }
        return rows;
      }
      return [];
    }

    function objectPanelTeamHtml(payload = {}) {
      return objectPanelTeamSectionHtml(objectPanelTeamRows(payload));
    }

    function objectPanelScopeContentModuleHtml(options = {}) {
      const title = String(options?.title || '').trim();
      const field = String(options?.field || '').trim();
      const objectId = String(options?.objectId || '').trim();
      const valueRaw = options?.value ?? '';
      const value = String(valueRaw);
      const editable = !!options?.editable;
      if (!title || !field || !objectId) return '';
      const inputId = `panelScopeContent_${field}_${objectId}`;
      return `
        <div class='module-fields module-body object-panel-scope-content-module'>
          <div class='panel-details-title'>${escapeHtml(title)}</div>
          ${
            editable
              ? `<textarea id='${inputId}' data-scope-content-field='${field}' rows='5'>${escapeHtml(value)}</textarea>`
              : `<div class='sub'>${value.trim() ? escapeHtmlMultiline(value) : '-'}</div>`
          }
        </div>
      `;
    }

    function objectPanelScopeContentHtml(payload = {}) {
      const type = String(payload?.module_type || '').toLowerCase().trim();
      if (type !== 'scope') return '';
      const scope = payload?.scope || {};
      const objectId = String(scope?.id || scope?.display_id || '').trim();
      if (!objectId) return '';
      const editMode = isModuleEditing('scope', objectId);
      const editable = editMode
        && (
          canUseControl('create_deal', currentRole)
          || canUseControl('ops_approve_latest_deal', currentRole)
          || canUseControl('manage_campaign_assignments', currentRole)
        );
      return [
        objectPanelScopeContentModuleHtml({
          title: 'ICP',
          field: 'icp',
          objectId,
          value: scope?.icp || '',
          editable,
        }),
        objectPanelScopeContentModuleHtml({
          title: 'Campaign Objective',
          field: 'campaign_objective',
          objectId,
          value: scope?.campaign_objective || '',
          editable,
        }),
        objectPanelScopeContentModuleHtml({
          title: 'Messaging',
          field: 'messaging_positioning',
          objectId,
          value: scope?.messaging_positioning || '',
          editable,
        }),
      ].join('');
    }

    function objectPanelProgressHtml(payload = {}) {
      const type = String(payload?.module_type || '').toLowerCase().trim();
      let progress = null;
      if (type === 'scope') {
        progress = deriveScopeCampaignProgress(payload?.scope || {});
      } else if (type === 'campaign') {
        progress = deriveCampaignStageProgress(payload?.campaign || {});
      } else if (type === 'stage') {
        const stage = payload?.stage || {};
        const stageSteps = Array.isArray(payload?.stage_steps)
          ? payload.stage_steps
          : (Array.isArray(stage?.steps) ? stage.steps : []);
        progress = renderSegmentedProgress(stageSteps.map(s => normalizeStatusValue(s?.status || s?.step_state || 'not_started')));
      }
      if (!progress) return '';
      return `
        <div class='module-fields module-body object-panel-progress-module'>
          <div class='panel-details-title'>Progress</div>
          <div class='card-progress span-2'>
            <div class='progress-meta'><span class='progress-label'>Overall progress</span><span class='progress-pct'>${panelPercentText(progress.pct)}</span></div>
            ${progress.barHtml}
          </div>
        </div>
      `;
    }

    function stepModuleCard(item, opts = {}) {
      const step = item?.step || {};
      const stageRef = item?.stage || {};
      const stepId = step.id || '-';
      const stepObjId = step.id || '';
      const due = step.current_due ? niceDate(step.current_due) : 'No due date';
      const start = step.current_start ? niceDate(step.current_start) : '-';
      const health = step.health || 'not_started';
      const status = step.status || stepStateFromItem(item);
      const ownerInitials = step.owner_initials || '--';
      const participants = Array.isArray(step.participant_initials) ? step.participant_initials : [];
      const ownerName = userName(step.next_owner_user_id);
      const participantPills = participants.length
        ? participants.map(p => userPill(p, false, null)).join('')
        : "<span class='sub'>None</span>";
      const campaignText = item?.campaign?.id ? `${item.campaign.id} · ${item.campaign.title || ''}` : '-';
      const linkedDeliverableTitle = step.linked_deliverable_title || step.deliverable_title || '-';
      const linkedDeliverableId = step.linked_deliverable_id || null;
      const canManageStep = (opts.showControls || canUseControl('manage_step', currentRole));
      const panelMode = !!opts.panel;
      const editMode = (panelMode || !opts.popover) && isModuleEditing('step', stepObjId);
      const showControls = canManageStep;
      const canEditOwner = canManageStep && editMode && !panelMode;
      const canEditStepDates = (panelMode || !opts.popover)
        && (canUseControl('manage_step_dates', currentRole) || canUseControl('override_step_due', currentRole))
        && editMode;
      const idPrefix = String(opts.idPrefix || opts.dropdownContext || 'step').replace(/[^a-zA-Z0-9_-]/g, '_');
      const stepStartId = opts.startId || `${idPrefix}Start_${step.id || 'step'}`;
      const stepDueId = opts.dueId || `${idPrefix}Due_${step.id || 'step'}`;
      const statusId = opts.statusId || `${idPrefix}Action_${step.id || 'step'}`;
      const ownerId = opts.ownerId || `${idPrefix}Owner_${step.id || 'step'}`;
      const reasonId = opts.reasonId || `${idPrefix}Reason_${step.id || 'step'}`;
      const statusControl = showControls
        ? `
          <input type='hidden' id='${statusId}' data-status-hidden='1' value='${status}' />
          ${statusPillDropdown({
            id: `statusDrop_${statusId || step.id || 'step'}`,
            current: status,
            options: GLOBAL_STATUS_OPTIONS,
            objectType: 'step',
            objectId: step.id || '',
            context: opts.dropdownContext || 'queue',
            ariaLabel: `Status for ${step.name || "step"}`,
          })}
        `
        : readonlyStatusPillDropdown(status, 'step', step.id || '');
      const ownerControl = canEditOwner
        ? `
          <input type='hidden' id='${ownerId}' data-owner-hidden='1' value='${step.next_owner_user_id || ''}' />
          ${ownerPillDropdown({
            id: `ownerDrop_${ownerId || step.id || 'step'}`,
            currentUserId: step.next_owner_user_id || '',
            users: usersDirectory.map(u => ({ id: u.id, name: u.name, initials: (u.initials || initialsFromName(u.name || '')) })),
            objectType: 'step',
            objectId: step.id || '',
            context: opts.dropdownContext || 'queue',
            hiddenInputId: ownerId || '',
            ariaLabel: `Owner for ${step.name || "step"}`,
          })}
        `
        : `<span>${userName(step.next_owner_user_id)}</span>`;
      const reasonControl = canEditOwner
        ? `<input id='${reasonId}' placeholder='Optional note' value='${String(step.blocker_reason || '').replace(/'/g, '&#39;')}' />`
        : `<span>${step.blocker_reason || '-'}</span>`;
      const actionButton = canEditOwner
        ? `<button onclick="${opts.onSave || ''}">Save</button>`
        : '';
      const openAttr = opts.popover ? '' : (opts.expanded ? 'open' : '');
      const openButton = moduleOpenButtonHtml(opts);
      const subtitle = cardSlotEnabled('step', 'subtitle') ? `${String(step.step_kind || 'task').replace(/_/g, ' ')} · ${String(step.owner_role || '-').toUpperCase()}` : '';
      const campaignSummaryId = item?.campaign?.id || step.campaign_id || '-';
      const wrapperTag = opts.popover ? 'div' : 'details';
      const headTag = opts.popover ? 'div' : 'summary';
      const wrapperBaseClass = opts.popover ? 'module-popover' : 'module-card';
      const wrapperExtraClass = opts.popover ? ' module-popover-static' : '';
      const wrapperEditClass = editMode && !opts.popover ? ' is-editing' : '';
      const chevronHtml = opts.popover ? '' : "<span class='module-chevron'>▸</span>";
      const summaryParts = [
        `<span class='summary-pill-slot slot-status' data-slot='status'>${statusChip(status)}</span>`,
        `<span class='summary-pill-slot slot-health' data-slot='health'>${healthChip(health)}</span>`,
        `<span class='module-summary-text summary-secondary summary-slot slot-timeframe_start' data-slot='timeframe_start'>${start !== '-' ? `${start} →` : ''}</span>`,
        `<span class='module-summary-text summary-secondary summary-slot slot-timeframe_end' data-slot='timeframe_end'>${due}</span>`,
        `<span class='summary-owner summary-slot slot-owner' data-slot='owner'>${userPill(ownerInitials, true, ownerName === '-' ? null : ownerName, { userId: step.next_owner_user_id || '' })}</span>`,
        `<span class='module-summary-text summary-secondary summary-slot slot-stage' data-slot='stage'>${formatStageLabel(step.stage || step.stage_name || '', '')}</span>`,
        `<span class='module-summary-right summary-slot slot-campaign_id' data-slot='campaign_id'>${campaignSummaryId}</span>`,
      ].filter(Boolean).join('');
      const summaryInlineHtml = opts.popover ? '' : `<div class='module-summary-inline module-summary-grid step-summary-grid'>${summaryParts}</div>`;
      const footer = moduleFooterHtml('step', {
        statusHtml: statusChip(status),
        avatarsHtml: moduleAvatarStack([
          { initials: ownerInitials || '--', name: ownerName === '-' ? '' : ownerName },
          ...participants.map(p => ({ initials: p, name: '' })),
        ]),
        dueText: due && due !== 'No due date' ? `Due ${due}` : '',
        actionsHtml: openButton || '',
      });
      const stageObjectId = String(stageRef?.id || stageRef?.display_id || step.stage_id || '').trim();
      const stageName = panelDetailValueText(formatStageLabel(stageRef?.name || step.stage_name || step.stage || '-', '-'), '-');
      const campaignId = String(item?.campaign?.id || step.campaign_id || '').trim();
      const campaignName = panelDetailValueText(item?.campaign?.title || item?.campaign?.campaign_name || campaignId || '-', '-');
      const stepProgress = renderSegmentedProgress([status]);
      const panelStatusControl = (canManageStep && editMode)
        ? `
          <input type='hidden' id='${statusId}' data-status-hidden='1' value='${status}' />
          ${statusPillDropdown({
            id: `panelStatusDrop_${step.id || 'step'}`,
            current: status,
            options: GLOBAL_STATUS_OPTIONS,
            objectType: 'step',
            objectId: step.id || '',
            context: 'panel',
            ariaLabel: `Status for ${step.name || "step"}`,
          })}
        `
        : statusChip(status);
      const panelOwnerControl = (canEditOwner && editMode)
        ? `
          <input type='hidden' id='${ownerId}' data-owner-hidden='1' value='${step.next_owner_user_id || ''}' />
          ${ownerPillDropdown({
            id: `panelOwnerDrop_${step.id || 'step'}`,
            currentUserId: step.next_owner_user_id || '',
            users: usersDirectory.map(u => ({ id: u.id, name: u.name, initials: (u.initials || initialsFromName(u.name || '')) })),
            objectType: 'step',
            objectId: step.id || '',
            context: 'panel',
            hiddenInputId: ownerId || '',
            ariaLabel: `Owner for ${step.name || "step"}`,
          })}
        `
        : `${userPill(ownerInitials, true, ownerName === '-' ? null : ownerName, { userId: step.next_owner_user_id || '' })}<span>${escapeHtml(panelDetailValueText(ownerName, '-'))}</span>`;
      const panelTimeframeControl = (canEditStepDates && editMode)
        ? `
          <input id='${stepStartId}' type='date' value='${(step.current_start || '').slice(0, 10)}' />
          <span>to</span>
          <input id='${stepDueId}' type='date' value='${(step.current_due || '').slice(0, 10)}' />
        `
        : `<span>${escapeHtml(panelTimeframeText(step.current_start, step.current_due))}</span>`;
      const panelDetailsHtml = panelMode
        ? panelDetailsSection([
            { label: 'Owner', valueHtml: panelOwnerControl },
            { label: 'Timeframe', valueHtml: panelTimeframeControl },
            { label: 'Status', valueHtml: panelStatusControl },
            { label: 'Progress', valueHtml: `<span>${panelPercentText(stepProgress.pct)}</span>` },
            { label: 'Health', valueHtml: healthChip(health) },
            { label: 'Stage', valueHtml: stageObjectId ? panelDetailLink(stageName, 'stage', stageObjectId, campaignId) : `<span>${escapeHtml(stageName)}</span>` },
            { label: 'Campaign', valueHtml: campaignId ? panelDetailLink(campaignName, 'campaign', campaignId, campaignId) : `<span>${escapeHtml(campaignName)}</span>` },
          ])
        : '';
      return `
        <${wrapperTag} class='${wrapperBaseClass}${wrapperExtraClass}${wrapperEditClass}' data-module='step' data-obj-type='step' data-obj-id='${step.id || ''}' data-campaign-id='${campaignSummaryId}' data-deliverable-id='${linkedDeliverableId || ''}' data-editing='${editMode ? '1' : '0'}' ${openAttr}>
          <${headTag} class='module-head'>
            <div class='module-head-left'>
              ${chevronHtml}
              <span class='module-icon'>${moduleIcon('step')}</span>
              <div class='module-title-block'>
                <div class='module-title'>${step.name || '-'}</div>
                ${subtitle ? `<div class='module-subtitle'>${subtitle}</div>` : ''}
              </div>
              ${summaryInlineHtml}
            </div>
            <div class='module-head-right'>
              ${moduleHeadRight('step', stepObjId, opts)}
            </div>
          </${headTag}>
          <div class='module-fields module-body'>
            ${panelMode && canManageStep && editMode ? `<input type='hidden' id='${reasonId}' value='${String(step.blocker_reason || '').replace(/'/g, '&#39;')}' />` : ''}
            ${panelDetailsHtml}
            ${panelMode ? '' : `
            ${cardSlotEnabled('step', 'description') && step.blocker_reason ? `<div class='module-row span-2'><span>Description:</span><span>${step.blocker_reason}</span></div>` : ''}
            ${cardSlotEnabled('step', 'key_values') ? `
            ${(cardSlotEnabled('step', 'step_status') || cardSlotEnabled('step', 'step_health')) ? `
            <div class='module-row'>
              ${cardSlotEnabled('step', 'step_status') ? `<span>Status:</span>${statusControl}` : ''}
              ${cardSlotEnabled('step', 'step_health') ? `<span>Health:</span>${healthChip(health)}` : ''}
            </div>
            ` : ''}
            ${cardSlotEnabled('step', 'timeframe') ? `
            <div class='module-row'>
              <span>Timeframe:</span>
              ${canEditStepDates
                ? `<input id='${stepStartId}' type='date' value='${(step.current_start || '').slice(0, 10)}' />
                   <span>to</span>
                   <input id='${stepDueId}' type='date' value='${(step.current_due || '').slice(0, 10)}' />
                   <button onclick="saveStepDates('${step.id}', '${stepStartId}', '${stepDueId}')">Save dates</button>`
                : `<span>${start} → ${due}</span>`
              }
            </div>
            ` : ''}
            ${(cardSlotEnabled('step', 'owner') || cardSlotEnabled('step', 'step_id')) ? `
            <div class='module-row'>
              ${cardSlotEnabled('step', 'owner') ? `<span>Owner:</span>${canEditOwner ? ownerControl : `${userPill(ownerInitials, true, ownerName === '-' ? null : ownerName, { userId: step.next_owner_user_id || '' })} <span>${ownerName}</span>`}` : ''}
              ${cardSlotEnabled('step', 'step_id') ? `<span>Step ID:</span><span><code>${stepId}</code></span>` : ''}
            </div>
            ` : ''}
            ${cardSlotEnabled('step', 'assigned_users') ? `<div class='module-row'><span>Assigned:</span>${participantPills}</div>` : ''}
            ${cardSlotEnabled('step', 'campaign_ref') ? `<div class='module-row span-2'><span>Campaign:</span><span>${campaignText || '-'}</span></div>` : ''}
            ${cardSlotEnabled('step', 'linked_deliverable') ? `<div class='module-row span-2'><span>Linked deliverable:</span><span>${linkedDeliverableTitle || '-'}</span></div>` : ''}
            ${cardSlotEnabled('step', 'note') ? `<div class='module-row span-2'><span>Note:</span>${reasonControl}${actionButton}</div>` : ''}
            ` : ''}
            ${cardSlotEnabled('step', 'tags') ? `<div class='module-row span-2'><span>Tags:</span><div class='card-tags'><span class='tag'>${formatStageLabel(step.stage || step.stage_name || 'stage', 'Stage')}</span><span class='tag'>${String(step.step_kind || 'task')}</span></div></div>` : ''}
            `}
          </div>
          ${footer}
        </${wrapperTag}>
      `;
    }

    function deriveStageStatus(steps) {
      const arr = Array.isArray(steps) ? steps : [];
      if (!arr.length) return 'not_started';
      const statuses = arr.map(s => normalizeStatusValue(s?.status || s?.step_state || 'not_started'));
      if (statuses.includes('blocked_client')) return 'blocked_client';
      if (statuses.includes('blocked_internal')) return 'blocked_internal';
      if (statuses.includes('blocked_dependency')) return 'blocked_dependency';
      if (statuses.includes('on_hold')) return 'on_hold';
      if (statuses.every(s => s === 'done' || s === 'cancelled')) return 'done';
      if (statuses.some(s => s === 'in_progress' || s === 'done')) return 'in_progress';
      return 'not_started';
    }

    function deriveStageHealth(steps) {
      const arr = Array.isArray(steps) ? steps : [];
      if (!arr.length) return 'not_started';
      const healths = arr.map(s => String(s?.health || 'not_started').toLowerCase());
      if (healths.includes('off_track')) return 'off_track';
      if (healths.includes('at_risk')) return 'at_risk';
      if (healths.includes('on_track')) return 'on_track';
      return 'not_started';
    }

    function stepWindowStart(step) {
      return (
        step?.current_start
        || step?.timeframe_start
        || step?.sow_start_date
        || step?.start_date
        || step?.current_due
        || step?.timeframe_due
        || step?.sow_end_date
        || step?.due_date
        || null
      );
    }

    function stepWindowEnd(step) {
      return (
        step?.current_due
        || step?.timeframe_due
        || step?.sow_end_date
        || step?.due_date
        || step?.current_start
        || step?.timeframe_start
        || step?.sow_start_date
        || step?.start_date
        || null
      );
    }

    function deriveStageWindowBounds(steps) {
      const arr = Array.isArray(steps) ? steps : [];
      const starts = arr.map(s => stepWindowStart(s)).filter(Boolean).sort();
      const ends = arr.map(s => stepWindowEnd(s)).filter(Boolean).sort();
      return {
        start: starts.length ? starts[0] : null,
        end: ends.length ? ends[ends.length - 1] : null,
      };
    }

    function deriveStageTimeframe(steps) {
      const bounds = deriveStageWindowBounds(steps);
      const start = bounds.start ? niceDate(bounds.start) : '-';
      const due = bounds.end ? niceDate(bounds.end) : '-';
      return `${start} → ${due}`;
    }

    function deriveStageDue(steps) {
      const bounds = deriveStageWindowBounds(steps);
      return bounds.end ? niceDate(bounds.end) : '-';
    }

    function deriveCampaignStageProgress(campaign) {
      const c = campaign || {};
      const providedStages = Array.isArray(c.stages) ? c.stages : [];
      if (providedStages.length) {
        const statuses = providedStages.map(s => normalizeStatusValue(s?.status || 'not_started'));
        return renderSegmentedProgress(statuses);
      }
      const grouped = {};
      const steps = Array.isArray(c.work_steps) ? c.work_steps : [];
      for (const step of steps) {
        const key = String(step?.stage || step?.stage_name || 'planning').toLowerCase();
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(step);
      }
      const stageKeys = Object.keys(grouped);
      if (!stageKeys.length) return { done: 0, total: 0, pct: 0, barHtml: "<div class='progress-track segmented'></div>" };
      const statuses = [];
      for (const key of stageKeys) {
        const stStatus = deriveStageStatus(grouped[key]);
        statuses.push(normalizeStatusValue(stStatus || 'not_started'));
      }
      return renderSegmentedProgress(statuses);
    }

    function deriveScopeCampaignProgress(scope) {
      const campaigns = Array.isArray(scope?.campaigns) ? scope.campaigns : [];
      const statuses = campaigns.map(c => normalizeStatusValue(c?.status || c?.campaign_status || 'not_started'));
      return renderSegmentedProgress(statuses);
    }

    function stageModuleCard(stage, opts = {}) {
      const s = stage || {};
      const stageObjId = s.id || '';
      const panelMode = !!opts.panel;
      const editMode = (panelMode || !opts.popover) && isModuleEditing('stage', stageObjId);
      const stageId = s.id || '-';
      const stageSteps = Array.isArray(s.steps) ? s.steps : [];
      const status = s.status || deriveStageStatus(stageSteps);
      const health = s.health || deriveStageHealth(stageSteps);
      const explicitStart = s.timeframe_start || s.current_start || s.baseline_start || null;
      const explicitDue = s.timeframe_due || s.current_due || s.baseline_due || null;
      const explicitTimeframe = (explicitStart || explicitDue)
        ? `${explicitStart ? niceDate(explicitStart) : '-'} → ${explicitDue ? niceDate(explicitDue) : '-'}`
        : '';
      const timeframe = s.timeframe || explicitTimeframe || deriveStageTimeframe(stageSteps);
      const dueOnly = s.due || (explicitDue ? niceDate(explicitDue) : '') || deriveStageDue(stageSteps);
      const summaryCampaignId = s.campaign_id || s.campaign?.id || '-';
      const summaryParts = [
        `<span class='summary-pill-slot slot-status' data-slot='status'>${statusChip(status)}</span>`,
        `<span class='summary-pill-slot slot-health' data-slot='health'>${healthChip(health)}</span>`,
        `<span class='module-summary-text summary-secondary summary-slot slot-timeframe_start' data-slot='timeframe_start'>${timeframe && timeframe.includes('→') ? `${timeframe.split('→')[0].trim()} →` : ''}</span>`,
        `<span class='module-summary-text summary-secondary summary-slot slot-timeframe_end' data-slot='timeframe_end'>${dueOnly}</span>`,
        `<span class='module-summary-right summary-slot slot-campaign_id' data-slot='campaign_id'>${summaryCampaignId}</span>`,
      ].join('');
      const summaryInlineHtml = opts.popover ? '' : `<div class='module-summary-inline module-summary-grid stage-summary-grid'>${summaryParts}</div>`;
      const stepsSummary = `${stageSteps.length} step${stageSteps.length === 1 ? '' : 's'}`;
      const openAttr = opts.popover ? '' : (opts.expanded ? 'open' : '');
      const openButton = moduleOpenButtonHtml(opts);
      const subtitle = cardSlotEnabled('stage', 'subtitle') ? `${stepsSummary}` : '';
      const wrapperTag = opts.popover ? 'div' : 'details';
      const headTag = opts.popover ? 'div' : 'summary';
      const wrapperBaseClass = opts.popover ? 'module-popover' : 'module-card';
      const wrapperExtraClass = opts.popover ? ' module-popover-static' : '';
      const wrapperEditClass = editMode && !opts.popover ? ' is-editing' : '';
      const chevronHtml = opts.popover ? '' : "<span class='module-chevron'>▸</span>";
      const stageProgress = renderSegmentedProgress(stageSteps.map(s => normalizeStatusValue(s?.status || s?.step_state || 'not_started')));
      const footer = moduleFooterHtml('stage', {
        statusHtml: statusChip(status),
        dueText: dueOnly && dueOnly !== '-' ? `Due ${dueOnly}` : '',
        actionsHtml: openButton || '',
      });
      const campaignName = panelDetailValueText(s.campaign_name || '-', '-');
      const panelDetailsHtml = panelMode
        ? panelDetailsSection([
            { label: 'Timeframe', valueHtml: `<span>${escapeHtml(panelDetailValueText(timeframe, '-'))}</span>` },
            { label: 'Status', valueHtml: readonlyStatusPillDropdown(status, 'stage', s.id || s.name || '') },
            { label: 'Health', valueHtml: healthChip(health) },
            { label: 'Campaign', valueHtml: summaryCampaignId && summaryCampaignId !== '-' ? panelDetailLink(campaignName, 'campaign', summaryCampaignId, summaryCampaignId) : `<span>${escapeHtml(campaignName)}</span>` },
          ])
        : '';
      const showStageStatus = cardSlotEnabled('stage', 'stage_status');
      const showStageHealth = cardSlotEnabled('stage', 'stage_health');
      const showTimeframe = cardSlotEnabled('stage', 'timeframe');
      const showCampaignName = cardSlotEnabled('stage', 'campaign_name');
      const showStageId = cardSlotEnabled('stage', 'stage_id');
      const showSteps = cardSlotEnabled('stage', 'list') && cardSlotEnabled('stage', 'steps');
      return `
        <${wrapperTag} class='${wrapperBaseClass}${wrapperExtraClass}${wrapperEditClass}' data-module='stage' data-obj-type='stage' data-obj-id='${s.id || ''}' data-campaign-id='${summaryCampaignId}' data-editing='${editMode ? '1' : '0'}' ${openAttr}>
          <${headTag} class='module-head'>
            <div class='module-head-left'>
              ${chevronHtml}
              <span class='module-icon'>${moduleIcon('stage')}</span>
              <div class='module-title-block'>
                <div class='module-title'>${s.name || '-'}</div>
                ${subtitle ? `<div class='module-subtitle'>${subtitle}</div>` : ''}
              </div>
              ${summaryInlineHtml}
            </div>
            <div class='module-head-right'>
              ${moduleHeadRight('stage', s.id || '', opts)}
            </div>
          </${headTag}>
          <div class='module-fields module-body'>
            ${panelDetailsHtml}
            ${panelMode ? '' : `
            ${cardSlotEnabled('stage', 'progress') ? `
              <div class='card-progress span-2'>
                <div class='progress-meta'><span class='progress-label'>Overall progress</span><span class='progress-pct'>${stageProgress.pct}%</span></div>
                ${stageProgress.barHtml}
              </div>
            ` : ''}
            ${cardSlotEnabled('stage', 'key_values') ? `
            ${(showStageStatus || showStageHealth) ? `
            <div class='module-row'>
              ${showStageStatus ? `<span>Status:</span>${readonlyStatusPillDropdown(status, 'stage', s.id || s.name || '')}` : ''}
              ${showStageHealth ? `<span>Health:</span>${healthChip(health)}` : ''}
            </div>` : ''}
            ${showTimeframe ? `
            <div class='module-row'>
              <span>Timeframe:</span><span>${timeframe}</span>
            </div>` : ''}
            ${(showCampaignName || showStageId) ? `
            <div class='module-row'>
              ${showCampaignName ? `<span>Campaign:</span><span>${s.campaign_name || '-'}</span>` : ''}
              ${showStageId ? `<span>Stage ID:</span><span><code>${stageId}</code></span>` : ''}
            </div>` : ''}
            ${opts.popover ? '' : `
              ${showSteps ? `
              <div class='module-row span-2' style='display:block;'>
                <div class='sub' style='margin-bottom:6px;'>${stepsSummary}</div>
                <div style='display:grid; gap:8px;'>
                  ${opts.stepsHtml || "<div class='sub'>No steps.</div>"}
                </div>
              </div>
              ` : ''}
            `}
            ` : ''}
            ${cardSlotEnabled('stage', 'tags') ? `<div class='module-row span-2'><span>Tags:</span><div class='card-tags'><span class='tag'>stage</span><span class='tag'>${formatStageLabel(s.name || '-', '-')}</span></div></div>` : ''}
            `}
          </div>
          ${footer}
        </${wrapperTag}>
      `;
    }

    function campaignModuleCard(campaign, opts = {}) {
      const c = campaign || {};
      const campaignObjId = c.id || c.campaign_id || '';
      const scopeId = c.scope_id || '-';
      const panelMode = !!opts.panel;
      const showDeleteAction = !opts.popover && !!opts.showDeleteAction && currentRole === 'head_ops' && canUseControl('delete_campaign', currentRole);
      const editMode = (panelMode || !opts.popover) && isModuleEditing('campaign', campaignObjId);
      const canManageCampaignAssignments = (panelMode || !opts.popover) && canUseControl('manage_campaign_assignments', currentRole) && editMode;
      const campaignStatus = normalizeStatusValue(c.status || c.campaign_status || 'not_started');
      const canManageCampaignStatus = canUseControl('manage_campaign_status', currentRole);
      const canManageCampaignDates = (panelMode || !opts.popover) && canUseControl('manage_campaign_dates', currentRole) && editMode;
      const idPrefix = String(opts.idPrefix || 'campaign').replace(/[^a-zA-Z0-9_-]/g, '_');
      const campaignStartId = opts.startId || `${idPrefix}Start_${c.id || c.campaign_id || 'campaign'}`;
      const campaignEndId = opts.endId || `${idPrefix}End_${c.id || c.campaign_id || 'campaign'}`;
      const assigned = Array.isArray(c.assigned_users) ? c.assigned_users : [];
      const roleLabel = { am: 'AM', cm: 'CM', cc: 'CC', ccs: 'CCS', dn: 'DN', mm: 'MM' };
      const assignedByRole = {};
      for (const a of assigned) {
        const key = String(a.role || '').toLowerCase();
        if (!key) continue;
        assignedByRole[key] = a;
      }
      const campaignOwner = assignedByRole.cm || null;
      const campaignOwnerInitials = campaignOwner?.initials || initialsFromName(campaignOwner?.name || '');
      const campaignOwnerSummary = campaignOwner
        ? userPill(campaignOwnerInitials || '--', true, campaignOwner.name || null, { userId: campaignOwner.user_id || campaignOwner.id || '', roleKey: 'cm' })
        : `<span class='tag warn'>Unassigned</span>`;
      const campaignOwnerDetail = campaignOwner
        ? `${userPill(campaignOwnerInitials || '--', true, campaignOwner.name || null, { userId: campaignOwner.user_id || campaignOwner.id || '', roleKey: 'cm' })} <span>${campaignOwner.name || '-'}</span>`
        : `<span class='tag warn'>Unassigned</span>`;
      const assignmentControl = (roleKey, label) => {
        const current = assignedByRole[roleKey] || {};
        const hiddenId = `${idPrefix}Assign_${c.id || c.campaign_id || 'campaign'}_${roleKey}`;
        const usersForRole = usersForAssignmentSlot(roleKey)
          .map(u => ({ id: u.id, name: u.name, initials: (u.initials || initialsFromName(u.name || '')) }));
        if (!canManageCampaignAssignments) {
          const initials = current.initials || initialsFromName(current.name || '');
          return `<div><span class='tag neutral'>${label || roleLabel[roleKey]}</span> ${userPill(initials || '--', true, current.name || null, { userId: current.user_id || current.id || '', roleKey })}</div>`;
        }
        return `
          <div>
            <input type='hidden' id='${hiddenId}' data-campaign-assign-hidden='1' data-role-key='${roleKey}' value='${current.user_id || ''}' />
            <span class='tag neutral' title='${label || roleLabel[roleKey]}'>${label || roleLabel[roleKey]}</span> ${ownerPillDropdown({
            id: `campAssignDrop_${c.id || c.campaign_id || 'campaign'}_${roleKey}`,
            currentUserId: current.user_id || '',
            users: usersForRole,
            objectType: 'campaign_assignment',
            objectId: c.id || c.campaign_id || '',
            context: 'campaigns',
            hiddenInputId: hiddenId,
            roleKey,
            ariaLabel: `${roleLabel[roleKey]} assignment for ${c.title || c.campaign_name || 'campaign'}`,
            })}
            ${usersForRole.length ? '' : `<span class='tag warn' style='margin-left:6px;'>No ${teamLabel(teamForAssignmentSlot(roleKey))} users</span>`}
          </div>
        `;
      };
      const assignmentListHtml = `
        <div style='display:grid; gap:8px;'>
          <div style='display:grid; grid-template-columns:1fr 1fr; gap:12px;'>
            ${assignmentControl('am', 'AM')}
            ${assignmentControl('cm', 'CM')}
          </div>
          <div style='display:grid; grid-template-columns:1fr 1fr; gap:12px;'>
            ${assignmentControl('cc', 'Lead CC')}
            ${assignmentControl('ccs', 'CC Support')}
          </div>
          <div style='display:grid; grid-template-columns:1fr 1fr; gap:12px;'>
            ${assignmentControl('dn', 'DN')}
            ${assignmentControl('mm', 'MM')}
          </div>
        </div>
      `;
      const timeframe = `${c.timeframe_start ? niceDate(c.timeframe_start) : '-'} → ${c.timeframe_due ? niceDate(c.timeframe_due) : '-'}`;
      const dueOnly = c.timeframe_due ? niceDate(c.timeframe_due) : '-';
      const isDemand = String(c.type || '').toLowerCase() === 'demand';
      const demandTrack = c.sprint_label
        ? `Create/Reach ${c.sprint_label}`
        : (String(c.demand_track || '').toLowerCase() === 'capture' ? 'Capture (Annual)' : '-');
      const deliverables = Array.isArray(c.deliverables) ? c.deliverables : [];
      const workSteps = Array.isArray(c.work_steps) ? c.work_steps : [];
      const summary = c.deliverables_summary || {};
      const deliverableSummaryText = `${Number(summary.total || deliverables.length || 0)} deliverables · Not started ${Number(summary.not_started || 0)} · In progress ${Number(summary.in_progress || 0)} · Done ${Number(summary.done || 0)}`;
      const showDeliverablesAccordion = !opts.popover && (Array.isArray(c.deliverables) || Boolean(c.deliverables_summary));
      const showStageCards = !opts.popover && Array.isArray(c.work_steps);
      const deliverablesAccordion = `
        <details class='ops-accordion surface-2'>
          <summary>Deliverables · ${deliverableSummaryText}</summary>
          <div style='padding:8px 10px; display:grid; gap:8px;'>
            ${deliverables.map(d => deliverableModuleCard(d, { idPrefix: `campaign_${c.id || c.campaign_id || 'campaign'}` })).join('') || "<div class='sub'>No deliverables.</div>"}
          </div>
        </details>
      `;
      const stageCardsHtml = (() => {
        const order = ['planning', 'production', 'promotion', 'reporting'];
        const labels = {
          planning: 'Planning',
          production: 'Production',
          promotion: 'Promotion',
          reporting: 'Reporting',
        };
        const grouped = { planning: [], production: [], promotion: [], reporting: [] };
        for (const s of workSteps) {
          const key = String(s.stage || s.deliverable_stage || 'planning').toLowerCase();
          if (grouped[key]) grouped[key].push(s);
          else grouped.planning.push(s);
        }
        const stages = order
          .filter(key => grouped[key].length > 0)
          .map(key => {
            const stageSteps = grouped[key];
            const stepCards = stageSteps.map(s => stepModuleCard({
              step: s,
              deliverable: { title: s.deliverable_title || '-' },
              campaign: { id: c.id || c.campaign_id || '-', title: c.title || c.campaign_name || '-' },
              derived: { is_overdue: !!(s.current_due && s.current_due < isoDate(new Date())) },
            }, {
              idPrefix: `campaign_${c.id || c.campaign_id || 'campaign'}`,
            })).join('') || "<div class='sub'>No steps.</div>";
            return stageModuleCard({
              id: `${c.id || c.campaign_id || 'campaign'}_${key}`,
              name: labels[key] || key,
              steps: stageSteps,
              campaign_id: c.id || c.campaign_id || '-',
              campaign_name: c.title || c.campaign_name || '-',
            }, { stepsHtml: stepCards });
          })
          .join('');
        return stages || "<div class='sub'>No work items.</div>";
      })();
      const summaryInlineHtml = opts.popover
        ? ''
        : `<div class='module-summary-inline module-summary-grid campaign-summary-inline'>
            <span class='summary-pill-slot slot-status' data-slot='status'>${statusChip(campaignStatus)}</span>
            <span class='summary-pill-slot slot-health' data-slot='health'>${healthChip(c.health || c.campaign_health || 'not_started')}</span>
            <span class='module-summary-text summary-secondary summary-slot slot-timeframe_start' data-slot='timeframe_start'>${c.timeframe_start ? `${niceDate(c.timeframe_start)} →` : ''}</span>
            <span class='module-summary-text summary-secondary summary-slot slot-timeframe_end' data-slot='timeframe_end'>${dueOnly}</span>
            <span class='module-summary-text summary-secondary summary-slot slot-owner' data-slot='owner'>${campaignOwnerSummary}</span>
            <span class='module-summary-text summary-secondary summary-slot slot-demand_track' data-slot='demand_track'>${isDemand ? demandTrack : ''}</span>
            <span class='module-summary-right summary-slot slot-campaign_id' data-slot='campaign_id'>${c.id || c.campaign_id || '-'}</span>
          </div>`;
      const subtitle = cardSlotEnabled('campaign', 'subtitle')
        ? `${toTitle(c.type || '')}${c.tier ? ` · ${toTitle(c.tier)}` : ''}`
        : '';
      const stageProgress = deriveCampaignStageProgress(c);
      const progressPct = Number(stageProgress.pct || 0);
      const statusControl = canManageCampaignStatus
        ? `
          <input type='hidden' id='campStatus_${c.id || c.campaign_id || ''}' data-campaign-status-hidden='1' value='${campaignStatus}' />
          ${statusPillDropdown({
            id: `campStatusDrop_${c.id || c.campaign_id || 'campaign'}`,
            current: campaignStatus,
            options: GLOBAL_STATUS_OPTIONS,
            objectType: 'campaign',
            objectId: c.id || c.campaign_id || '',
            context: 'campaigns',
            ariaLabel: `Status for ${c.title || c.campaign_name || 'campaign'}`,
          })}
        `
        : readonlyStatusPillDropdown(campaignStatus, 'campaign', c.id || c.campaign_id || '');
      const openAttr = opts.popover ? '' : (opts.expanded ? 'open' : '');
      const openButton = moduleOpenButtonHtml(opts);
      const wrapperTag = opts.popover ? 'div' : 'details';
      const headTag = opts.popover ? 'div' : 'summary';
      const wrapperBaseClass = opts.popover ? 'module-popover' : 'module-card';
      const wrapperExtraClass = opts.popover ? ' module-popover-static' : '';
      const chevronHtml = opts.popover ? '' : "<span class='module-chevron'>▸</span>";
      const footer = moduleFooterHtml('campaign', {
        statusHtml: statusChip(campaignStatus),
        avatarsHtml: moduleAvatarStack(assigned.map(a => ({ initials: a.initials || initialsFromName(a.name || ''), name: a.name || '' }))),
        dueText: c.timeframe_due ? `Due ${niceDate(c.timeframe_due)}` : '',
        actionsHtml: openButton || '',
      });
      const cmAssignHiddenId = `${idPrefix}Assign_${c.id || c.campaign_id || 'campaign'}_cm`;
      const panelAssignmentHiddenInputs = ['am', 'cc', 'ccs', 'dn', 'mm']
        .map(roleKey => {
          const existing = assignedByRole[roleKey] || {};
          return `<input type='hidden' id='${idPrefix}Assign_${c.id || c.campaign_id || 'campaign'}_${roleKey}' data-campaign-assign-hidden='1' data-role-key='${roleKey}' value='${existing.user_id || ''}' />`;
        })
        .join('');
      const panelCampaignOwnerControl = (canManageCampaignAssignments && editMode)
        ? `
          ${panelAssignmentHiddenInputs}
          <input type='hidden' id='${cmAssignHiddenId}' data-campaign-assign-hidden='1' data-role-key='cm' value='${campaignOwner?.user_id || ''}' />
          ${ownerPillDropdown({
            id: `panelCampaignOwnerDrop_${c.id || c.campaign_id || 'campaign'}`,
            currentUserId: campaignOwner?.user_id || '',
            users: usersForAssignmentSlot('cm').map(u => ({ id: u.id, name: u.name, initials: (u.initials || initialsFromName(u.name || '')) })),
            objectType: 'campaign_assignment',
            objectId: c.id || c.campaign_id || '',
            context: 'panel',
            hiddenInputId: cmAssignHiddenId,
            roleKey: 'cm',
            ariaLabel: `Owner for ${c.title || c.campaign_name || 'campaign'}`,
          })}
        `
        : (campaignOwner
          ? `${userPill(campaignOwnerInitials || '--', true, campaignOwner.name || null, { userId: campaignOwner.user_id || campaignOwner.id || '', roleKey: 'cm' })}<span>${escapeHtml(panelDetailValueText(campaignOwner.name || '-', '-'))}</span>`
          : `<span class='tag warn'>Unassigned</span>`);
      const panelCampaignTimeframeControl = (canManageCampaignDates && editMode)
        ? `<input id='${campaignStartId}' type='date' value='${(c.timeframe_start || '').slice(0, 10)}' /><span>to</span><input id='${campaignEndId}' type='date' value='${(c.timeframe_due || '').slice(0, 10)}' />`
        : `<span>${escapeHtml(panelTimeframeText(c.timeframe_start, c.timeframe_due))}</span>`;
      const panelCampaignStatusControl = (canManageCampaignStatus && editMode)
        ? `
          <input type='hidden' id='campStatus_${c.id || c.campaign_id || ''}' data-campaign-status-hidden='1' value='${campaignStatus}' />
          ${statusPillDropdown({
            id: `campPanelStatusDrop_${c.id || c.campaign_id || 'campaign'}`,
            current: campaignStatus,
            options: GLOBAL_STATUS_OPTIONS,
            objectType: 'campaign',
            objectId: c.id || c.campaign_id || '',
            context: 'panel',
            ariaLabel: `Status for ${c.title || c.campaign_name || 'campaign'}`,
          })}
        `
        : statusChip(campaignStatus);
      const panelDetailsRows = [
        { label: 'Product', valueHtml: `<span>${escapeHtml(panelDetailValueText(toTitle(c.type || '-'), '-'))}</span>` },
        { label: 'Level', valueHtml: `<span>${escapeHtml(panelDetailValueText(toTitle(c.tier || '-'), '-'))}</span>` },
        ...(isDemand ? [{ label: 'Track', valueHtml: `<span>${escapeHtml(panelDetailValueText(demandTrack, '-'))}</span>` }] : []),
        { label: 'Owner', valueHtml: panelCampaignOwnerControl },
        { label: 'Timeframe', valueHtml: panelCampaignTimeframeControl },
        { label: 'Status', valueHtml: panelCampaignStatusControl },
        { label: 'Health', valueHtml: healthChip(c.health || c.campaign_health || 'not_started') },
        { label: 'Scope', valueHtml: scopeId && scopeId !== '-' ? panelDetailLink(scopeId, 'scope', scopeId) : `<span>${escapeHtml(panelDetailValueText(scopeId, '-'))}</span>` },
      ];
      const panelDetailsHtml = panelMode ? panelDetailsSection(panelDetailsRows) : '';
      return `
        <${wrapperTag} class='${wrapperBaseClass}${wrapperExtraClass}' data-module='campaign' data-obj-type='campaign' data-obj-id='${c.id || c.campaign_id || ''}' data-campaign-id='${c.id || c.campaign_id || ''}' ${openAttr}>
          <${headTag} class='module-head'>
            <div class='module-head-left'>
              ${chevronHtml}
              <span class='module-icon'>${moduleIcon('campaign')}</span>
              <div class='module-title-block'>
                <div class='module-title'>${c.title || c.campaign_name || '-'}</div>
                ${subtitle ? `<div class='module-subtitle'>${subtitle}</div>` : ''}
              </div>
              ${summaryInlineHtml}
            </div>
            <div class='module-head-right'>
              ${moduleHeadRight('campaign', campaignObjId, opts)}
            </div>
          </${headTag}>
          <div class='module-fields module-body'>
            ${panelDetailsHtml}
            ${panelMode ? '' : `
            ${cardSlotEnabled('campaign', 'progress') ? `
              <div class='card-progress span-2'>
                <div class='progress-meta'><span class='progress-label'>Overall progress</span><span class='progress-pct'>${progressPct}%</span></div>
                ${stageProgress.barHtml}
              </div>
            ` : ''}
            ${cardSlotEnabled('campaign', 'key_values') ? `
            ${(cardSlotEnabled('campaign', 'campaign_status') || cardSlotEnabled('campaign', 'campaign_health')) ? `<div class='module-row'>${cardSlotEnabled('campaign', 'campaign_status') ? `<span>Status:</span>${statusControl}` : ''}${cardSlotEnabled('campaign', 'campaign_health') ? `<span>Health:</span>${healthChip(c.health || c.campaign_health || 'not_started')}` : ''}</div>` : ''}
            ${cardSlotEnabled('campaign', 'owner') ? `<div class='module-row'><span>Owner:</span>${campaignOwnerDetail}</div>` : ''}
            ${isDemand && cardSlotEnabled('campaign', 'demand_track') ? `<div class='module-row'><span>Track:</span><span>${demandTrack}</span></div>` : ''}
            ${cardSlotEnabled('campaign', 'timeframe') ? `<div class='module-row'><span>Timeframe:</span>${canManageCampaignDates ? `<input id='${campaignStartId}' type='date' value='${(c.timeframe_start || '').slice(0, 10)}' /><span>to</span><input id='${campaignEndId}' type='date' value='${(c.timeframe_due || '').slice(0, 10)}' /><button onclick="saveCampaignDates('${c.id || c.campaign_id}', '${campaignStartId}', '${campaignEndId}')">Save dates</button>` : `<span>${timeframe}</span>`}</div>` : ''}
            ${cardSlotEnabled('campaign', 'users_assigned') ? `<div class='module-row span-2' style='display:block;'><span class='campaign-meta-label'>Users assigned:</span>${assignmentListHtml}</div>` : ''}
            ${cardSlotEnabled('campaign', 'scope_id') ? `<div class='module-row span-2'><span>Scope ID:</span><span><code>${scopeId}</code></span></div>` : ''}
            ${cardSlotEnabled('campaign', 'campaign_id') ? `<div class='module-row span-2'><span>Campaign ID:</span><span><code>${c.id || c.campaign_id || '-'}</code></span></div>` : ''}
            ` : ''}
            ${cardSlotEnabled('campaign', 'list') && cardSlotEnabled('campaign', 'work') && showStageCards ? `
              <div class='module-row span-2' style='display:block;'>
                <div style='display:grid; gap:8px;'>
                  ${stageCardsHtml}
                </div>
              </div>
            ` : ''}
            ${cardSlotEnabled('campaign', 'list') && cardSlotEnabled('campaign', 'deliverables') && showDeliverablesAccordion ? `
              <div class='module-row span-2' style='display:block;'>
                ${deliverablesAccordion}
              </div>
            ` : ''}
            ${cardSlotEnabled('campaign', 'tags') ? `<div class='module-row span-2'><span>Tags:</span><div class='card-tags'><span class='tag'>${toTitle(c.type || '-')}</span>${c.tier ? `<span class='tag'>${toTitle(c.tier)}</span>` : ''}${isDemand ? `<span class='tag'>${demandTrack}</span>` : ''}</div></div>` : ''}
            `}
          </div>
          ${footer}
        </${wrapperTag}>
      `;
    }

    function deliverableModuleCard(deliverable, opts = {}) {
      const d = deliverable || {};
      const deliverableObjId = d.id || '';
      const deliverableId = d.id || '-';
      const campaignName = d.campaign_name || d.campaign_title || d.campaign?.title || '-';
      const campaignSummaryId = d.campaign_id || d.campaign?.id || '-';
      const start = d.current_start ? niceDate(d.current_start) : '-';
      const due = d.current_due ? niceDate(d.current_due) : '-';
      const ownerName = userName(d.owner_user_id);
      const ownerInitials = d.owner_initials || (d.owner_user_id ? initialsFromName(ownerName || '') : '--');
      const panelMode = !!opts.panel;
      const editMode = (panelMode || !opts.popover) && isModuleEditing('deliverable', deliverableObjId);
      const canManageDeliverableDates = (panelMode || !opts.popover) && canUseControl('manage_deliverable_dates', currentRole) && editMode;
      const canManageDeliverableOwner = canUseControl('manage_deliverable_owner', currentRole) && editMode;
      const canAdvanceDeliverableStatus = canUseControl('advance_deliverable', currentRole);
      const idPrefix = String(opts.idPrefix || 'deliverable').replace(/[^a-zA-Z0-9_-]/g, '_');
      const deliverableStartId = opts.startId || `${idPrefix}Start_${d.id || 'deliverable'}`;
      const deliverableDueId = opts.dueId || `${idPrefix}Due_${d.id || 'deliverable'}`;
      const deliverableOwnerId = opts.ownerId || `${idPrefix}Owner_${d.id || 'deliverable'}`;
      const stageLabel = formatStageLabel(d.stage || 'planning', 'Planning');
      const actionRow = opts.actionsHtml ? `<div class='actions'>${opts.actionsHtml}</div>` : '';
      const statusControl = opts.statusControlHtml || (canAdvanceDeliverableStatus
        ? deliverableStatusDropdown(d, opts.dropdownContext || 'deliverables')
        : readonlyStatusPillDropdown(d.status || 'not_started', 'deliverable', d.id || ''));
      const ownerControl = opts.ownerControlHtml || (canManageDeliverableOwner
        ? `
          <input type='hidden' id='${deliverableOwnerId}' data-owner-hidden='1' value='${d.owner_user_id || ''}' />
          ${ownerPillDropdown({
            id: `delOwnerDrop_${d.id || 'deliverable'}`,
            currentUserId: d.owner_user_id || '',
            users: usersDirectory.map(u => ({ id: u.id, name: u.name, initials: (u.initials || initialsFromName(u.name || '')) })),
            objectType: 'deliverable',
            objectId: d.id || '',
            context: opts.dropdownContext || 'deliverables',
            hiddenInputId: deliverableOwnerId,
            ariaLabel: `Owner for ${d.title || "deliverable"}`,
          })}
        `
        : `${userPill(ownerInitials, true, ownerName === '-' ? null : ownerName, { userId: d.owner_user_id || '' })} <span>${ownerName}</span>`);
      const dueControl = opts.dueControlHtml
        ? `<div class='module-row span-2'><span>Due date:</span>${opts.dueControlHtml}</div>`
        : '';
      const stageControl = opts.stageControlHtml
        ? `<div class='module-row span-2'><span>Current stage:</span>${opts.stageControlHtml}</div>`
        : `<div class='module-row'><span>Current stage:</span><span>${stageLabel}</span></div>`;
      const openAttr = opts.popover ? '' : (opts.expanded ? 'open' : '');
      const openButton = moduleOpenButtonHtml(opts);
      const wrapperTag = opts.popover ? 'div' : 'details';
      const headTag = opts.popover ? 'div' : 'summary';
      const wrapperBaseClass = opts.popover ? 'module-popover' : 'module-card';
      const wrapperExtraClass = opts.popover ? ' module-popover-static' : '';
      const wrapperEditClass = editMode && !opts.popover ? ' is-editing' : '';
      const chevronHtml = opts.popover ? '' : "<span class='module-chevron'>▸</span>";
      const summaryParts = [
        `<span class='summary-pill-slot slot-status' data-slot='status'>${statusChip(d.status || 'not_started')}</span>`,
        `<span class='module-summary-text summary-secondary summary-slot slot-timeframe_start' data-slot='timeframe_start'>${start !== '-' ? `${start} →` : ''}</span>`,
        `<span class='module-summary-text summary-secondary summary-slot slot-timeframe_end' data-slot='timeframe_end'>${due}</span>`,
        `<span class='summary-owner summary-slot slot-owner' data-slot='owner'>${userPill(ownerInitials, true, ownerName === '-' ? null : ownerName, { userId: d.owner_user_id || '' })}</span>`,
        `<span class='module-summary-text summary-secondary summary-slot slot-stage' data-slot='stage'>${stageLabel}</span>`,
        `<span class='module-summary-right summary-slot slot-campaign_id' data-slot='campaign_id'>${campaignSummaryId}</span>`,
      ].join('');
      const summaryInlineHtml = opts.popover ? '' : `<div class='module-summary-inline module-summary-grid deliverable-summary-grid'>${summaryParts}</div>`;
      const subtitle = cardSlotEnabled('deliverable', 'subtitle') ? `${toTitle(String(d.type || d.deliverable_type || 'deliverable'))}` : '';
      const footer = moduleFooterHtml('deliverable', {
        statusHtml: statusChip(d.status || 'not_started'),
        avatarsHtml: moduleAvatarStack([{ initials: ownerInitials || '--', name: ownerName === '-' ? '' : ownerName }]),
        dueText: d.current_due ? `Due ${niceDate(d.current_due)}` : '',
        actionsHtml: openButton || actionRow,
      });
      const showDeliverableStatus = cardSlotEnabled('deliverable', 'deliverable_status');
      const showOwner = cardSlotEnabled('deliverable', 'owner');
      const showTimeframe = cardSlotEnabled('deliverable', 'timeframe');
      const showCampaignName = cardSlotEnabled('deliverable', 'campaign_name');
      const showDeliverableId = cardSlotEnabled('deliverable', 'deliverable_id');
      const showStage = cardSlotEnabled('deliverable', 'stage');
      return `
        <${wrapperTag} class='${wrapperBaseClass}${wrapperExtraClass}${wrapperEditClass}' data-module='deliverable' data-obj-type='deliverable' data-obj-id='${d.id || ''}' data-campaign-id='${campaignSummaryId}' data-editing='${editMode ? '1' : '0'}' ${openAttr}>
          <${headTag} class='module-head'>
            <div class='module-head-left'>
              ${chevronHtml}
              <span class='module-icon'>${moduleIcon('deliverable')}</span>
              <div class='module-title-block'>
                <div class='module-title'>${d.title || '-'}</div>
                ${subtitle ? `<div class='module-subtitle'>${subtitle}</div>` : ''}
              </div>
              ${summaryInlineHtml}
            </div>
            <div class='module-head-right'>
              ${moduleHeadRight('deliverable', deliverableObjId, opts)}
            </div>
          </${headTag}>
          <div class='module-fields module-body'>
            ${cardSlotEnabled('deliverable', 'key_values') ? `
            ${showDeliverableStatus ? `<div class='module-row'><span>Status:</span>${statusControl}</div>` : ''}
            ${showOwner ? `<div class='module-row'><span>Owner:</span>${ownerControl}</div>` : ''}
            ${showTimeframe ? `<div class='module-row'>
              <span>Timeframe:</span>
              ${canManageDeliverableDates
                ? `<input id='${deliverableStartId}' type='date' value='${(d.current_start || '').slice(0, 10)}' />
                   <span>to</span>
                   <input id='${deliverableDueId}' type='date' value='${(d.current_due || '').slice(0, 10)}' />
                   <button onclick="saveDeliverableDates('${d.id}', '${deliverableStartId}', '${deliverableDueId}')">Save dates</button>`
                : `<span>${start} → ${due}</span>`
              }
            </div>` : ''}
            ${(showCampaignName || showDeliverableId) ? `<div class='module-row'>
              ${showCampaignName ? `<span>Associated campaign:</span><span>${campaignName}</span>` : ''}
              ${showDeliverableId ? `<span>Deliverable ID:</span><span><code>${deliverableId}</code></span>` : ''}
            </div>` : ''}
            ${showStage ? stageControl : ''}
            ${dueControl}
            ` : ''}
            ${cardSlotEnabled('deliverable', 'tags') ? `<div class='module-row span-2'><span>Tags:</span><div class='card-tags'><span class='tag'>${stageLabel}</span><span class='tag'>${toTitle(String(d.status || 'not_started'))}</span></div></div>` : ''}
          </div>
          ${footer}
        </${wrapperTag}>
      `;
    }

    function ownerSelectOptions(selectedId) {
      const options = ["<option value=''>Unassigned</option>"];
      for (const u of usersDirectory) {
        const selected = u.id === selectedId ? "selected" : "";
        options.push(`<option value="${u.id}" ${selected}>${u.name}</option>`);
      }
      return options.join('');
    }

    function deliverableStatusDropdown(deliverable, context = 'workspace') {
      const d = deliverable || {};
      const currentDeliveryStatus = String(d.delivery_status || 'planned').toLowerCase();
      const currentGlobalStatus = normalizeStatusValue(d.status || globalStatusFromDeliverableStatus(currentDeliveryStatus));
      const next = deliverableNextTransitions(currentDeliveryStatus);
      const options = [{ value: currentGlobalStatus, raw: currentDeliveryStatus }];
      const seenGlobals = new Set([currentGlobalStatus]);
      for (const nxt of next) {
        const gv = normalizeStatusValue(globalStatusFromDeliverableStatus(nxt));
        if (seenGlobals.has(gv)) continue;
        seenGlobals.add(gv);
        options.push({ value: gv, raw: nxt });
      }
      return `
        <input type='hidden' id='delStatus_${d.id}' data-delivery-status='1' value='${currentDeliveryStatus}' />
        ${statusPillDropdown({
          id: `delStatusDrop_${d.id}`,
          current: currentGlobalStatus,
          currentRaw: currentDeliveryStatus,
          options,
          objectType: 'deliverable',
          objectId: d.id || '',
          context,
          ariaLabel: `Status for ${d.title || 'deliverable'}`,
          disabled: !canUseControl('advance_deliverable', currentRole),
        })}
      `;
    }

    function rerenderCurrentListFromCache() {
      const screen = String(currentScreen || '').toLowerCase();
      if (screen === 'campaigns') {
        renderListModule('campaignsBody', LIST_ROWS_CACHE.campaigns || []);
        requestAnimationFrame(() => applyModuleLayoutRules(document.getElementById('campaignsBody') || document));
        return true;
      }
      if (screen === 'deals' || screen === 'scopes') {
        renderListModule('dealsBody', LIST_ROWS_CACHE.deals || []);
        requestAnimationFrame(() => applyModuleLayoutRules(document.getElementById('dealsBody') || document));
        return true;
      }
      return false;
    }

    function recomputeListRowProgress(row) {
      if (!row || !Array.isArray(row.children) || !row.children.length) return;
      for (const child of row.children) recomputeListRowProgress(child);
      const type = String(row.module_type || '').toLowerCase();
      if (type === 'stage') {
        row.progress_statuses = row.children
          .filter(ch => String(ch.module_type || '').toLowerCase() === 'step')
          .map(ch => normalizeStatusValue(ch.status || 'not_started'));
        row.status = normalizeStatusValue(deriveStageStatus(row.children || []));
        return;
      }
      if (type === 'campaign') {
        row.progress_statuses = row.children
          .filter(ch => String(ch.module_type || '').toLowerCase() === 'stage')
          .map(ch => normalizeStatusValue(ch.status || 'not_started'));
        return;
      }
      if (type === 'scope') {
        row.progress_statuses = row.children
          .filter(ch => String(ch.module_type || '').toLowerCase() === 'campaign')
          .map(ch => normalizeStatusValue(ch.status || 'not_started'));
      }
    }

    function updateListCachesForStatus(moduleType, objectId, newStatus, extras = {}) {
      const targetType = String(moduleType || '').toLowerCase();
      const targetId = String(objectId || '').trim();
      const normalized = normalizeStatusValue(newStatus || 'not_started');
      if (!targetType || !targetId) return false;
      let changed = false;
      const visit = (row) => {
        if (!row || typeof row !== 'object') return;
        const rowType = String(row.module_type || '').toLowerCase();
        const rowId = String(row.id || '').trim();
        if (rowType === targetType && rowId === targetId) {
          row.status = normalized;
          if (targetType === 'deliverable' && extras.delivery_status) row.delivery_status = String(extras.delivery_status).toLowerCase();
          changed = true;
        }
        if (Array.isArray(row.children)) {
          for (const child of row.children) visit(child);
        }
      };
      for (const root of (LIST_ROWS_CACHE.campaigns || [])) visit(root);
      for (const root of (LIST_ROWS_CACHE.deals || [])) visit(root);
      for (const root of (LIST_ROWS_CACHE.campaigns || [])) recomputeListRowProgress(root);
      for (const root of (LIST_ROWS_CACHE.deals || [])) recomputeListRowProgress(root);
      return changed;
    }

    function listStatusControl(row, moduleType, status) {
      const type = String(moduleType || '').toLowerCase();
      const objectId = String(row?.id || '').trim();
      const editable = (
        (type === 'step' && canUseControl('manage_step', currentRole)) ||
        (type === 'deliverable' && canUseControl('advance_deliverable', currentRole)) ||
        (type === 'campaign' && canUseControl('manage_campaign_status', currentRole))
      );
      if (!editable || !objectId || !status) return status ? statusChip(status) : '';
      if (type === 'deliverable') {
        const currentRaw = String(row?.delivery_status || deliverableRawStatusFromGlobal(status)).toLowerCase();
        const next = deliverableNextTransitions(currentRaw);
        const options = [{ value: normalizeStatusValue(globalStatusFromDeliverableStatus(currentRaw)), raw: currentRaw }];
        const seen = new Set(options.map(o => normalizeStatusValue(o.value)));
        for (const nxt of next) {
          const gv = normalizeStatusValue(globalStatusFromDeliverableStatus(nxt));
          if (seen.has(gv)) continue;
          seen.add(gv);
          options.push({ value: gv, raw: nxt });
        }
        return statusPillDropdown({
          id: `listDelStatusDrop_${objectId}`,
          current: status,
          currentRaw,
          options,
          objectType: 'deliverable',
          objectId,
          context: 'list',
          ariaLabel: `Status for ${String(row?.title || 'deliverable')}`,
        });
      }
      return statusPillDropdown({
        id: `listStatusDrop_${type}_${objectId}`,
        current: status,
        objectType: type,
        objectId,
        context: 'list',
        ariaLabel: `Status for ${String(row?.title || type)}`,
      });
    }

    function queueItemCard(item) {
      const controls = canUseControl('manage_step', currentRole)
        ? stepModuleCard(item, {
            showControls: true,
            idPrefix: 'queue',
            ownerId: `stepOwner_${item.step.id}`,
            statusId: `stepAction_${item.step.id}`,
            dropdownContext: 'queue',
            dueId: `stepDue_${item.step.id}`,
            startId: `stepStart_${item.step.id}`,
            reasonId: `stepReason_${item.step.id}`,
            onSave: `manageStepFromQueue('${item.step.id}')`,
          })
        : stepModuleCard(item, {});
      return controls;
    }

    function renderMyWorkFromCache() {
      if (!myWorkCache) return;
      const grid = document.getElementById('myWorkGrid');
      const rows = Array.isArray(myWorkCache?.list_items) ? myWorkCache.list_items : [];
      const modeEl = document.getElementById('myWorkMode');
      const mode = String(modeEl?.value || 'owned_only').toLowerCase();
      const filteredRows = rows.filter(row => (mode === 'owned_and_participant' ? true : !!row?.is_owned));
      if (!grid) return;
      if (!filteredRows.length) {
        grid.innerHTML = "<div class='sub'>No work items.</div>";
        const summaryEl = document.getElementById('myWorkSummary');
        if (summaryEl) summaryEl.textContent = 'No items in current view';
        return;
      }
      const bodyRows = filteredRows.map(row => `
        <tr>
          <td>${escapeHtml(String(row.item_name || '-'))}</td>
          <td>${escapeHtml(toTitle(String(row.type || '-')))}</td>
          <td>${escapeHtml(String(row.campaign || '-'))}</td>
          <td>${escapeHtml(toTitle(String(row.stage || '-')))}</td>
          <td>${row.due_date ? niceDate(row.due_date) : '-'}</td>
          <td>${escapeHtml(toTitle(String(row.status || '-').replaceAll('_', ' ')))}</td>
          <td>${healthChip(String(row.health || 'not_started'))}</td>
          <td>${escapeHtml(String(row.dependency_blocker || '-'))}</td>
          <td>${row.planned_work_date ? niceDate(row.planned_work_date) : '-'}</td>
        </tr>
      `).join('');
      grid.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Item name</th>
              <th>Type</th>
              <th>Campaign</th>
              <th>Stage</th>
              <th>Due date</th>
              <th>Status</th>
              <th>Health</th>
              <th>Dependency/Blocker</th>
              <th>Planned work date</th>
            </tr>
          </thead>
          <tbody>${bodyRows}</tbody>
        </table>
      `;
      const summaryEl = document.getElementById('myWorkSummary');
      if (summaryEl) summaryEl.textContent = `${filteredRows.length} items`;
    }

    async function renderMyWork(role, actorId) {
      const modeEl = document.getElementById('myWorkMode');
      const includeMode = String(modeEl?.value || 'owned_only');
      if (!actorId || actorId === 'null' || actorId === 'undefined') {
        myWorkCache = { summary: { total: 0 }, queues: {} };
        campaignHealthByCampaignId = {};
        renderMyWorkFromCache();
        return;
      }
      myWorkCache = await api(`/api/my-work?actor_user_id=${encodeURIComponent(actorId)}&role=${encodeURIComponent(role)}&include_mode=${encodeURIComponent(includeMode)}`);
      try {
        const health = await api(`/api/campaigns/health?owner=${encodeURIComponent(actorId)}&limit=500&offset=0`);
        campaignHealthByCampaignId = {};
        for (const item of (health.items || [])) {
          campaignHealthByCampaignId[item.campaign_id] = item;
        }
      } catch (_) {
        campaignHealthByCampaignId = {};
      }
      renderMyWorkFromCache();
    }

    async function manageStepFromQueue(stepId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        const actionEl = document.getElementById(`stepAction_${stepId}`);
        const reasonEl = document.getElementById(`stepReason_${stepId}`);
        const payload = {
          actor_user_id: currentActorId,
          status: actionEl?.value || 'in_progress',
          next_owner_user_id: ownerFieldValue(`stepOwner_${stepId}`),
          blocker_reason: reasonEl?.value || null,
        };
        const result = await api(`/api/workflow-steps/${stepId}/manage`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        log('Task updated', result);
        await renderMyWork(currentRole, currentActorId);
      } catch (err) {
        log('Task update failed', String(err));
      }
    }

    function teamForAssignmentSlot(roleKey) {
      const key = String(roleKey || '').toLowerCase();
      if (key === 'am') return 'sales';
      if (key === 'cc' || key === 'ccs') return 'editorial';
      if (key === 'dn' || key === 'mm') return 'marketing';
      if (key === 'cm') return 'client_services';
      return '';
    }

    function usersForAssignmentSlot(roleKey) {
      const team = teamForAssignmentSlot(roleKey);
      if (!team) return [];
      return usersDirectory.filter(u => String(u.primary_team || '').toLowerCase() === team);
    }

    function assignmentSelectOptionsForRole(roleKey, selectedId) {
      const options = ["<option value=''>Unassigned</option>"];
      const matches = usersForAssignmentSlot(roleKey);
      for (const u of matches) {
        const selected = u.id === selectedId ? "selected" : "";
        options.push(`<option value="${u.id}" ${selected}>${u.name}</option>`);
      }
      return options.join('');
    }

    async function saveCampaignAssignments() {
      try {
        if (!currentWorkspaceCampaignId) throw new Error('No campaign selected');
        if (!currentActorId) throw new Error('No active actor selected');
        if (!canUseControl('manage_campaign_assignments', currentRole)) {
          throw new Error('You do not have permission to update assignments');
        }
        const currentAssignments = (workspaceCache?.campaign?.assignments || {});
        const payload = {
          actor_user_id: currentActorId,
          am_user_id: document.getElementById('wsAssign_am')?.value || null,
          cm_user_id: document.getElementById('wsAssign_cm')?.value || null,
          cc_user_id: document.getElementById('wsAssign_cc')?.value || null,
          ccs_user_id: document.getElementById('wsAssign_ccs')?.value || null,
          dn_user_id: document.getElementById('wsAssign_dn')?.value || null,
          mm_user_id: document.getElementById('wsAssign_mm')?.value || null,
        };
        const slotDefs = [
          { key: 'am', label: 'AM', field: 'am_user_id' },
          { key: 'cm', label: 'CM', field: 'cm_user_id' },
          { key: 'cc', label: 'Lead CC', field: 'cc_user_id' },
          { key: 'ccs', label: 'CC Support', field: 'ccs_user_id' },
          { key: 'dn', label: 'DN', field: 'dn_user_id' },
          { key: 'mm', label: 'MM', field: 'mm_user_id' },
        ];
        const changedSlots = slotDefs
          .map(def => {
            const oldId = currentAssignments[def.key] || null;
            const newId = payload[def.field] || null;
            if (oldId === newId) return null;
            const oldName = oldId ? userName(oldId) : 'Unassigned';
            const newName = newId ? userName(newId) : 'Unassigned';
            return { ...def, oldId, newId, oldName, newName };
          })
          .filter(Boolean);

        payload.cascade_owner_updates = false;
        if (changedSlots.length) {
          const summary = changedSlots.map(s => `${s.label}: ${s.oldName} → ${s.newName}`).join('\\n');
          const cascadeYes = window.confirm(
            `Assignment changes:\n${summary}\n\nAlso update deliverable/step owners for matching role records currently owned by the previous assignee?\n\nOK = Yes (cascade)\nCancel = No/Cancel`
          );
          if (cascadeYes) {
            payload.cascade_owner_updates = true;
          } else {
            const saveWithoutCascade = window.confirm(
              `Save assignment changes without updating deliverable/step owners?

OK = Save without cascade
Cancel = Abort save`
            );
            if (!saveWithoutCascade) return;
          }
        }
        const result = await api(`/api/campaigns/${encodeURIComponent(currentWorkspaceCampaignId)}/assignments`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        log('Campaign assignments updated', result);
        if (workspaceCache?.campaign) {
          workspaceCache.campaign.assignments = {
            ...(workspaceCache.campaign.assignments || {}),
            am: payload.am_user_id,
            cm: payload.cm_user_id,
            cc: payload.cc_user_id,
            ccs: payload.ccs_user_id,
            dn: payload.dn_user_id,
            mm: payload.mm_user_id,
          };
        }
        const deliverableUpdates = Number(result.updated_deliverables_count || 0);
        const stepUpdates = Number(result.updated_steps_count || 0);
        if (result.cascade_applied) {
          toast(`Assignments saved · Owners cascaded (${deliverableUpdates} deliverables, ${stepUpdates} steps)`, 'success');
        } else {
          toast('Assignments saved', 'success');
        }
        await renderCapacity();
      } catch (err) {
        toast(`Unable to save assignments: ${String(err)}`, 'error');
        log('Campaign assignment update failed', String(err));
      }
    }

    async function saveDeliverableDue(deliverableId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        if (!canUseControl('override_step_due', currentRole)) {
          throw new Error('You do not have permission to edit due dates');
        }
        const input = document.getElementById(`delDue_${deliverableId}`);
        const rawValue = (input?.value || '').trim();
        if (!rawValue) throw new Error('Select a due date first');
        const value = nextWorkingIsoFromIso(rawValue);
        const result = await api(`/api/deliverables/${deliverableId}/override-due`, {
          method: 'POST',
          body: JSON.stringify({
            actor_user_id: currentActorId,
            current_due_iso: value,
            reason_code: 'schedule_adjustment',
          }),
        });
        if (input) input.value = String(result.current_due || value).slice(0, 10);
        workspaceCache = null;
        await Promise.all([renderCampaignWorkspace(), renderCapacity()]);
        toast('Deliverable due saved', 'success');
      } catch (err) {
        toast(`Unable to save deliverable due: ${String(err)}`, 'error');
        log('Deliverable due update failed', String(err));
      }
    }

    async function saveStepDates(stepId, startInputId, dueInputId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        if (!(canUseControl('manage_step_dates', currentRole) || canUseControl('override_step_due', currentRole))) {
          throw new Error('You do not have permission to edit step dates');
        }
        const startRaw = (document.getElementById(startInputId)?.value || '').trim();
        const dueRaw = (document.getElementById(dueInputId)?.value || '').trim();
        if (!startRaw && !dueRaw) throw new Error('Select at least one date');
        const result = await api(`/api/workflow-steps/${stepId}/manage`, {
          method: 'PATCH',
          body: JSON.stringify({
            actor_user_id: currentActorId,
            current_start_iso: startRaw ? nextWorkingIsoFromIso(startRaw) : null,
            current_due_iso: dueRaw ? nextWorkingIsoFromIso(dueRaw) : null,
          }),
        });
        const startEl = document.getElementById(startInputId);
        const dueEl = document.getElementById(dueInputId);
        if (startEl && result.current_start) startEl.value = String(result.current_start).slice(0, 10);
        if (dueEl && result.current_due) dueEl.value = String(result.current_due).slice(0, 10);
        const campaignsState = currentScreen === 'campaigns' ? captureCampaignsViewState() : null;
        toast('Step dates saved', 'success');
        await Promise.all([renderCampaigns(), renderMyWork(currentRole, currentActorId), renderCapacity()]);
        await restoreCampaignsViewState(campaignsState);
      } catch (err) {
        toast(`Unable to save step dates: ${String(err)}`, 'error');
        log('Step dates update failed', String(err));
      }
    }

    async function saveDeliverableDates(deliverableId, startInputId, dueInputId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        if (!canUseControl('manage_deliverable_dates', currentRole)) {
          throw new Error('You do not have permission to edit deliverable dates');
        }
        const startRaw = (document.getElementById(startInputId)?.value || '').trim();
        const dueRaw = (document.getElementById(dueInputId)?.value || '').trim();
        if (!startRaw && !dueRaw) throw new Error('Select at least one date');
        const result = await api(`/api/deliverables/${deliverableId}/dates`, {
          method: 'PATCH',
          body: JSON.stringify({
            actor_user_id: currentActorId,
            current_start_iso: startRaw ? nextWorkingIsoFromIso(startRaw) : null,
            current_due_iso: dueRaw ? nextWorkingIsoFromIso(dueRaw) : null,
            reason_code: 'schedule_adjustment',
          }),
        });
        const startEl = document.getElementById(startInputId);
        const dueEl = document.getElementById(dueInputId);
        if (startEl && result.current_start) startEl.value = String(result.current_start).slice(0, 10);
        if (dueEl && result.current_due) dueEl.value = String(result.current_due).slice(0, 10);
        const campaignsState = currentScreen === 'campaigns' ? captureCampaignsViewState() : null;
        toast('Deliverable dates saved', 'success');
        await Promise.all([renderCampaigns(), renderDeliverables(), renderCapacity()]);
        await restoreCampaignsViewState(campaignsState);
      } catch (err) {
        toast(`Unable to save deliverable dates: ${String(err)}`, 'error');
        log('Deliverable dates update failed', String(err));
      }
    }

    async function saveCampaignDates(campaignId, startInputId, endInputId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        if (!canUseControl('manage_campaign_dates', currentRole)) {
          throw new Error('You do not have permission to edit campaign dates');
        }
        const startRaw = (document.getElementById(startInputId)?.value || '').trim();
        const endRaw = (document.getElementById(endInputId)?.value || '').trim();
        if (!startRaw && !endRaw) throw new Error('Select at least one date');
        const result = await api(`/api/campaigns/${encodeURIComponent(campaignId)}/dates`, {
          method: 'PATCH',
          body: JSON.stringify({
            actor_user_id: currentActorId,
            planned_start_iso: startRaw ? nextWorkingIsoFromIso(startRaw) : null,
            planned_end_iso: endRaw ? nextWorkingIsoFromIso(endRaw) : null,
          }),
        });
        const startEl = document.getElementById(startInputId);
        const endEl = document.getElementById(endInputId);
        if (startEl && result.planned_start_date) startEl.value = String(result.planned_start_date).slice(0, 10);
        if (endEl && result.planned_end_date) endEl.value = String(result.planned_end_date).slice(0, 10);
        const campaignsState = currentScreen === 'campaigns' ? captureCampaignsViewState() : null;
        toast('Campaign dates saved', 'success');
        await Promise.all([renderCampaigns(), renderCapacity()]);
        await restoreCampaignsViewState(campaignsState);
      } catch (err) {
        toast(`Unable to save campaign dates: ${String(err)}`, 'error');
        log('Campaign dates update failed', String(err));
      }
    }

    async function saveDeliverableStage(deliverableId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        if (!canUseControl('edit_deliverable_stage', currentRole)) {
          throw new Error('You do not have permission to edit stage');
        }
        const stage = (document.getElementById(`delStage_${deliverableId}`)?.value || '').trim().toLowerCase();
        if (!stage) throw new Error('Select a stage');
        await api(`/api/deliverables/${deliverableId}/stage`, {
          method: 'PATCH',
          body: JSON.stringify({
            actor_user_id: currentActorId,
            stage,
          }),
        });
        workspaceCache = null;
        await Promise.all([renderCampaignWorkspace(), renderDeliverables()]);
        toast('Deliverable stage saved', 'success');
      } catch (err) {
        toast(`Unable to save deliverable stage: ${String(err)}`, 'error');
        log('Deliverable stage update failed', String(err));
      }
    }

    async function manageWorkspaceStep(stepId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        if (!canUseControl('manage_step', currentRole)) {
          throw new Error('You do not have permission to manage steps');
        }
        const dueRaw = (document.getElementById(`wsStepDue_${stepId}`)?.value || '').trim();
        const payload = {
          actor_user_id: currentActorId,
          status: document.getElementById(`wsStepAction_${stepId}`)?.value || 'in_progress',
          next_owner_user_id: ownerFieldValue(`wsStepOwner_${stepId}`),
          waiting_on_user_id: null,
          blocker_reason: document.getElementById(`wsStepReason_${stepId}`)?.value || null,
          current_due_iso: dueRaw ? nextWorkingIsoFromIso(dueRaw) : null,
        };
        const result = await api(`/api/workflow-steps/${stepId}/manage`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        log('Workspace step updated', result);
        workspaceCache = null;
        await Promise.all([renderCampaignWorkspace(), renderMyWork(currentRole, currentActorId), renderCapacity()]);
        toast('Step saved', 'success');
      } catch (err) {
        toast(`Unable to save step: ${String(err)}`, 'error');
        log('Workspace step update failed', String(err));
      }
    }

    function statusContextIds(stepId, context) {
      if (context === 'workspace') {
        return {
          ownerId: `wsStepOwner_${stepId}`,
          reasonId: `wsStepReason_${stepId}`,
          dueId: `wsStepDue_${stepId}`,
          hiddenStatusId: `wsStepAction_${stepId}`,
        };
      }
      if (context === 'panel') {
        return {
          ownerId: `panelStepOwner_${stepId}`,
          reasonId: `panelStepReason_${stepId}`,
          dueId: `panelStepDue_${stepId}`,
          hiddenStatusId: `panelStepAction_${stepId}`,
        };
      }
      if (context === 'task') {
        return {
          ownerId: `taskOwner_${stepId}`,
          reasonId: `taskReason_${stepId}`,
          dueId: `taskDue_${stepId}`,
          hiddenStatusId: `taskAction_${stepId}`,
        };
      }
      return {
        ownerId: `stepOwner_${stepId}`,
        reasonId: `stepReason_${stepId}`,
        dueId: `stepDue_${stepId}`,
        hiddenStatusId: `stepAction_${stepId}`,
      };
    }

    function ownerFieldValue(fieldId) {
      if (!fieldId) return null;
      const el = document.getElementById(fieldId);
      if (!el) return null;
      return (el.value || '').trim() || null;
    }

    async function autoSaveStepStatusFromDropdown(stepId, newStatus, context, dropdownEl) {
      if (!currentActorId) {
        toast('No active actor selected', 'error');
        return;
      }
      if (!canUseControl('manage_step', currentRole)) {
        toast('You do not have permission to update step status', 'error');
        return;
      }
      const ids = statusContextIds(stepId, context);
      const statusHidden = document.getElementById(ids.hiddenStatusId);
      const previousStatus = normalizeStatusValue(statusHidden?.value || dropdownEl?.getAttribute('data-current-status') || 'not_started');
      const targetStatus = normalizeStatusValue(newStatus || previousStatus);
      if (targetStatus === previousStatus) {
        closeAllPillDropdowns();
        return;
      }

      setPillDropdownSaving(dropdownEl, true);
      try {
        const ownerId = ownerFieldValue(ids.ownerId);
        const reasonEl = ids.reasonId ? document.getElementById(ids.reasonId) : null;
        const dueEl = ids.dueId ? document.getElementById(ids.dueId) : null;
        const dueRaw = (dueEl?.value || '').trim();
        const payload = {
          actor_user_id: currentActorId,
          status: targetStatus,
          waiting_on_user_id: null,
          blocker_reason: reasonEl?.value || null,
          current_due_iso: dueRaw ? nextWorkingIsoFromIso(dueRaw) : null,
        };
        if (context !== 'list') payload.next_owner_user_id = ownerId;
        const result = await api(`/api/workflow-steps/${stepId}/manage`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        if (statusHidden) statusHidden.value = targetStatus;
        if (dropdownEl) dropdownEl.setAttribute('data-current-status', targetStatus);
        setPillDropdownValue(dropdownEl, targetStatus);
        if (dueEl && result.current_due) dueEl.value = String(result.current_due).slice(0, 10);
        closeAllPillDropdowns();
        toast('Step status updated', 'success');
        if (context === 'list') {
          updateListCachesForStatus('step', stepId, targetStatus);
          rerenderCurrentListFromCache();
        } else if (context === 'queue') {
          await renderMyWork(currentRole, currentActorId);
        } else {
          workspaceCache = null;
          await Promise.all([renderCampaignWorkspace(), renderMyWork(currentRole, currentActorId), renderCapacity()]);
        }
      } catch (err) {
        if (statusHidden) statusHidden.value = previousStatus;
        setPillDropdownValue(dropdownEl, previousStatus);
        toast(`Unable to update step status: ${String(err)}`, 'error');
        log('Auto step status update failed', String(err));
      } finally {
        setPillDropdownSaving(dropdownEl, false);
      }
    }

    async function autoSaveDeliverableStatusFromDropdown(deliverableId, rawStatus, globalStatus, dropdownEl) {
      if (!currentActorId) {
        toast('No active actor selected', 'error');
        return;
      }
      if (!canUseControl('advance_deliverable', currentRole)) {
        toast('You do not have permission to update deliverable status', 'error');
        return;
      }
      const hidden = document.getElementById(`delStatus_${deliverableId}`);
      const previousRaw = String(hidden?.value || dropdownEl?.getAttribute('data-current-raw') || '').toLowerCase();
      if (!rawStatus || String(rawStatus).toLowerCase() === previousRaw) {
        closeAllPillDropdowns();
        return;
      }
      setPillDropdownSaving(dropdownEl, true);
      try {
        const result = await api(`/api/deliverables/${deliverableId}/transition`, {
          method: 'POST',
          body: JSON.stringify({
            actor_user_id: currentActorId,
            to_status: String(rawStatus).toLowerCase(),
            comment: 'Status updated from pill dropdown',
          }),
        });
        if (hidden) hidden.value = String(result.delivery_status || rawStatus).toLowerCase();
        const resolvedRaw = String(result.delivery_status || rawStatus).toLowerCase();
        const resolvedGlobal = normalizeStatusValue(result.status || globalStatus);
        if (dropdownEl) dropdownEl.setAttribute('data-current-raw', resolvedRaw);
        setPillDropdownValue(dropdownEl, resolvedGlobal);
        closeAllPillDropdowns();
        toast('Deliverable status updated', 'success');
        if (String(dropdownEl?.getAttribute('data-context') || '').toLowerCase() === 'list') {
          updateListCachesForStatus('deliverable', deliverableId, resolvedGlobal, { delivery_status: resolvedRaw });
          rerenderCurrentListFromCache();
        } else {
          workspaceCache = null;
          await Promise.all([renderCampaignWorkspace(), renderDeliverables(), renderMyWork(currentRole, currentActorId)]);
        }
      } catch (err) {
        setPillDropdownValue(dropdownEl, normalizeStatusValue(globalStatusFromDeliverableStatus(previousRaw || 'planned')));
        toast(`Unable to update deliverable status: ${String(err)}`, 'error');
        log('Auto deliverable status update failed', String(err));
      } finally {
        setPillDropdownSaving(dropdownEl, false);
      }
    }

    async function autoSaveCampaignStatusFromDropdown(campaignId, newStatus, dropdownEl) {
      if (!currentActorId) {
        toast('No active actor selected', 'error');
        return;
      }
      if (!canUseControl('manage_campaign_status', currentRole)) {
        toast('You do not have permission to update campaign status', 'error');
        return;
      }
      const hidden = document.getElementById(`campStatus_${campaignId}`);
      const previousStatus = normalizeStatusValue(hidden?.value || dropdownEl?.getAttribute('data-current-status') || 'not_started');
      const targetStatus = normalizeStatusValue(newStatus || previousStatus);
      if (targetStatus === previousStatus) {
        closeAllPillDropdowns();
        return;
      }
      setPillDropdownSaving(dropdownEl, true);
      try {
        const result = await api(`/api/campaigns/${encodeURIComponent(campaignId)}/status`, {
          method: 'PATCH',
          body: JSON.stringify({
            actor_user_id: currentActorId,
            status: targetStatus,
          }),
        });
        const resolvedStatus = normalizeStatusValue(result.status || targetStatus);
        if (hidden) hidden.value = resolvedStatus;
        if (dropdownEl) dropdownEl.setAttribute('data-current-status', resolvedStatus);
        setPillDropdownValue(dropdownEl, resolvedStatus);
        closeAllPillDropdowns();
        toast('Campaign status updated', 'success');
        if (String(dropdownEl?.getAttribute('data-context') || '').toLowerCase() === 'list') {
          updateListCachesForStatus('campaign', campaignId, resolvedStatus);
          rerenderCurrentListFromCache();
        } else {
          await runCampaignAwareRefresh(async () => {
            await renderCampaigns();
          });
        }
      } catch (err) {
        if (hidden) hidden.value = previousStatus;
        setPillDropdownValue(dropdownEl, previousStatus);
        toast(`Unable to update campaign status: ${String(err)}`, 'error');
        log('Auto campaign status update failed', String(err));
      } finally {
        setPillDropdownSaving(dropdownEl, false);
      }
    }

    async function cascadeCampaignDescendantStatus(campaignId) {
      const cid = String(campaignId || '').trim();
      if (!cid) {
        toast('Campaign id missing', 'error');
        return;
      }
      if (!currentActorId) {
        toast('No active actor selected', 'error');
        return;
      }
      if (!canUseControl('manage_campaign_status', currentRole)) {
        toast('You do not have permission to cascade campaign statuses', 'error');
        return;
      }
      const allowed = ['not_started', 'in_progress', 'on_hold', 'blocked_client', 'blocked_internal', 'blocked_dependency', 'done', 'cancelled'];
      const typedStatus = String(window.prompt(
        `Cascade status to all steps under this campaign.\n\nAllowed values:\n${allowed.join(', ')}\n\nEnter status:`,
        'in_progress',
      ) || '').trim().toLowerCase();
      if (!typedStatus) return;
      if (!allowed.includes(typedStatus)) {
        toast('Unsupported status for cascade', 'error');
        return;
      }
      try {
        const preview = await api(`/api/campaigns/${encodeURIComponent(cid)}/status/cascade`, {
          method: 'POST',
          body: JSON.stringify({
            actor_user_id: currentActorId,
            status: typedStatus,
            dry_run: true,
          }),
        });
        const warning = `This will update ${preview.steps_to_update || 0} steps across ${preview.stages_impacted || 0} stages.\n\nType exactly:\n${preview.confirmation_required}\n\nto proceed.`;
        const confirmationPhrase = String(window.prompt(warning, '') || '').trim();
        if (!confirmationPhrase) return;
        await api(`/api/campaigns/${encodeURIComponent(cid)}/status/cascade`, {
          method: 'POST',
          body: JSON.stringify({
            actor_user_id: currentActorId,
            status: typedStatus,
            dry_run: false,
            confirmation_phrase: confirmationPhrase,
          }),
        });
        toast('Campaign descendant statuses updated', 'success');
        await runCampaignAwareRefresh(async () => {
          await renderCampaigns();
        });
        if (panelPayload && String(panelPayload?.module_type || '').toLowerCase() === 'campaign') {
          const refreshed = await fetchObjectPanelPayload('campaign', cid, cid);
          if (refreshed) openObjectPanelByPayload(refreshed);
        }
      } catch (err) {
        toast(`Unable to cascade status: ${String(err)}`, 'error');
        log('Campaign status cascade failed', String(err));
      }
    }

    function campaignAssignmentPayloadFromCard(campaignId, dropdownEl) {
      const campaignCard = dropdownEl?.closest(".module-card[data-module='campaign']");
      const hiddenInputs = Array.from(campaignCard?.querySelectorAll("input[data-campaign-assign-hidden='1']") || []);
      const byRole = {};
      for (const input of hiddenInputs) {
        const roleKey = String(input.getAttribute('data-role-key') || '').toLowerCase();
        if (!roleKey) continue;
        byRole[roleKey] = (input.value || '').trim() || null;
      }
      return {
        actor_user_id: currentActorId,
        am_user_id: byRole.am || null,
        cm_user_id: byRole.cm || null,
        cc_user_id: byRole.cc || null,
        ccs_user_id: byRole.ccs || null,
        dn_user_id: byRole.dn || null,
        mm_user_id: byRole.mm || null,
      };
    }

    function assignmentSlotLabel(roleKey) {
      const k = String(roleKey || '').toLowerCase();
      if (k === 'cc') return 'Lead CC';
      if (k === 'ccs') return 'CC Support';
      return k.toUpperCase();
    }

    async function autoSaveCampaignAssignmentFromDropdown(campaignId, roleKey, userId, initials, fullName, dropdownEl) {
      if (!currentActorId) {
        toast('No active actor selected', 'error');
        return;
      }
      if (!canUseControl('manage_campaign_assignments', currentRole)) {
        toast('You do not have permission to update campaign assignments', 'error');
        return;
      }
      const hiddenId = dropdownEl?.getAttribute('data-owner-hidden-id') || '';
      const hiddenEl = hiddenId ? document.getElementById(hiddenId) : null;
      const previousOwner = String(hiddenEl?.value || '');
      const nextOwner = String(userId || '').trim();
      if (previousOwner === nextOwner) {
        updateOwnerSelectionFromDropdown(dropdownEl, userId, initials, fullName);
        return;
      }

      if (hiddenEl) hiddenEl.value = nextOwner;
      setOwnerDropdownValue(dropdownEl, nextOwner, initials || '--', fullName || null);
      closeAllPillDropdowns();
      try {
        const payload = campaignAssignmentPayloadFromCard(campaignId, dropdownEl);
        payload.cascade_owner_updates = false;
        const oldName = previousOwner ? userName(previousOwner) : 'Unassigned';
        const newName = nextOwner ? userName(nextOwner) : 'Unassigned';
        const cascadeYes = window.confirm(
          `Assignment change:
${assignmentSlotLabel(roleKey)}: ${oldName} → ${newName}

Also update deliverable and step owners currently owned by ${oldName} for this role?

OK = Yes (cascade)
Cancel = No/Cancel`
        );
        if (cascadeYes) {
          payload.cascade_owner_updates = true;
        } else {
          const saveWithoutCascade = window.confirm(
            `Save assignment change without cascading owner updates?

OK = Save without cascade
Cancel = Abort`
          );
          if (!saveWithoutCascade) {
            if (hiddenEl) hiddenEl.value = previousOwner;
            const fallbackName = previousOwner ? userName(previousOwner) : null;
            const fallbackInitials = previousOwner ? initialsFromName(fallbackName || '') : '--';
            setOwnerDropdownValue(dropdownEl, previousOwner, fallbackInitials, fallbackName);
            return;
          }
        }
        await api(`/api/campaigns/${encodeURIComponent(campaignId)}/assignments`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        if (payload.cascade_owner_updates) toast('Campaign assignment updated with owner cascade', 'success');
        else toast('Campaign assignment updated', 'success');
        await runCampaignAwareRefresh(async () => {
          await Promise.all([renderCampaigns(), renderCapacity()]);
        });
      } catch (err) {
        if (hiddenEl) hiddenEl.value = previousOwner;
        const fallbackName = previousOwner ? userName(previousOwner) : null;
        const fallbackInitials = previousOwner ? initialsFromName(fallbackName || '') : '--';
        setOwnerDropdownValue(dropdownEl, previousOwner, fallbackInitials, fallbackName);
        toast(`Unable to update campaign assignment: ${String(err)}`, 'error');
        log('Auto campaign assignment update failed', String(err));
      }
    }

    function updateOwnerSelectionFromDropdown(dropdown, userId, initials, fullName) {
      if (!dropdown) return;
      setOwnerDropdownValue(dropdown, userId || '', initials || '--', fullName || null);
      closeAllPillDropdowns();
    }

    async function autoSaveStepOwnerFromDropdown(stepId, userId, initials, fullName, context, dropdownEl) {
      if (!currentActorId) {
        toast('No active actor selected', 'error');
        return;
      }
      if (!canUseControl('manage_step', currentRole)) {
        toast('You do not have permission to update step owner', 'error');
        return;
      }
      const ids = statusContextIds(stepId, context);
      const statusHidden = document.getElementById(ids.hiddenStatusId);
      const reasonEl = ids.reasonId ? document.getElementById(ids.reasonId) : null;
      const dueEl = ids.dueId ? document.getElementById(ids.dueId) : null;
      const dueRaw = (dueEl?.value || '').trim();
      const nextOwner = String(userId || '').trim() || null;
      const hiddenOwner = ids.ownerId ? document.getElementById(ids.ownerId) : null;
      const previousOwner = hiddenOwner ? (hiddenOwner.value || '') : '';
      if ((previousOwner || '') === (nextOwner || '')) {
        updateOwnerSelectionFromDropdown(dropdownEl, userId, initials, fullName);
        return;
      }

      if (hiddenOwner) hiddenOwner.value = nextOwner || '';
      setOwnerDropdownValue(dropdownEl, nextOwner || '', initials || '--', fullName || null);
      closeAllPillDropdowns();

      try {
        const payload = {
          actor_user_id: currentActorId,
          status: statusHidden?.value || 'in_progress',
          next_owner_user_id: nextOwner,
          waiting_on_user_id: null,
          blocker_reason: reasonEl?.value || null,
          current_due_iso: dueRaw ? nextWorkingIsoFromIso(dueRaw) : null,
        };
        const result = await api(`/api/workflow-steps/${stepId}/manage`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        if (dueEl && result.current_due) dueEl.value = String(result.current_due).slice(0, 10);
        toast('Step owner updated', 'success');
        if (context === 'queue') {
          await renderMyWork(currentRole, currentActorId);
        } else {
          workspaceCache = null;
          await runCampaignAwareRefresh(async () => {
            await Promise.all([renderCampaigns(), renderMyWork(currentRole, currentActorId), renderCapacity()]);
          });
        }
      } catch (err) {
        if (hiddenOwner) hiddenOwner.value = previousOwner;
        const fallbackName = previousOwner ? userName(previousOwner) : null;
        const fallbackInitials = previousOwner ? initialsFromName(fallbackName || '') : '--';
        setOwnerDropdownValue(dropdownEl, previousOwner, fallbackInitials, fallbackName);
        toast(`Unable to update step owner: ${String(err)}`, 'error');
        log('Auto step owner update failed', String(err));
      }
    }

    async function autoSaveDeliverableOwnerFromDropdown(deliverableId, userId, initials, fullName, context, dropdownEl) {
      if (!currentActorId) {
        toast('No active actor selected', 'error');
        return;
      }
      if (!canUseControl('manage_deliverable_owner', currentRole)) {
        toast('You do not have permission to update deliverable owner', 'error');
        return;
      }

      const ownerHidden = dropdownEl?.parentElement?.querySelector("input[type='hidden'][data-owner-hidden='1']");
      const previousOwner = String(ownerHidden?.value || '');
      const nextOwner = String(userId || '').trim();
      if (previousOwner === nextOwner) {
        updateOwnerSelectionFromDropdown(dropdownEl, userId, initials, fullName);
        return;
      }

      if (ownerHidden) ownerHidden.value = nextOwner;
      setOwnerDropdownValue(dropdownEl, nextOwner, initials || '--', fullName || null);
      closeAllPillDropdowns();
      try {
        const result = await api(`/api/deliverables/${deliverableId}/owner`, {
          method: 'PATCH',
          body: JSON.stringify({
            actor_user_id: currentActorId,
            owner_user_id: nextOwner || null,
          }),
        });
        const resolvedOwner = String(result.owner_user_id || nextOwner || '');
        if (ownerHidden) ownerHidden.value = resolvedOwner;
        const resolvedName = resolvedOwner ? userName(resolvedOwner) : null;
        const resolvedInitials = result.owner_initials || (resolvedOwner ? initialsFromName(resolvedName || '') : '--');
        setOwnerDropdownValue(dropdownEl, resolvedOwner, resolvedInitials, resolvedName);
        toast('Deliverable owner updated', 'success');
        await runCampaignAwareRefresh(async () => {
          await Promise.all([renderCampaigns(), renderDeliverables(), renderCapacity()]);
        });
      } catch (err) {
        if (ownerHidden) ownerHidden.value = previousOwner;
        const fallbackName = previousOwner ? userName(previousOwner) : null;
        const fallbackInitials = previousOwner ? initialsFromName(fallbackName || '') : '--';
        setOwnerDropdownValue(dropdownEl, previousOwner, fallbackInitials, fallbackName);
        toast(`Unable to update deliverable owner: ${String(err)}`, 'error');
        log('Auto deliverable owner update failed', String(err));
      }
    }

    function toast(msg, type = 'info') {
      const wrap = document.getElementById('toastWrap');
      const el = document.createElement('div');
      el.className = 'toast';
      if (type === 'error') el.style.background = '#7f1d1d';
      if (type === 'success') el.style.background = '#14532d';
      el.textContent = msg;
      wrap.appendChild(el);
      setTimeout(() => el.remove(), 2800);
    }

    function publicationLabel(value) {
      const map = {
        uc_today: 'UC Today',
        cx_today: 'CX Today',
        techtelligence: 'Techtelligence',
      };
      return map[value] || value;
    }

    function log(msg, data) {
      const el = document.getElementById('log');
      const text = data ? `${msg}: ${JSON.stringify(data, null, 2)}` : msg;
      el.textContent = `${new Date().toLocaleTimeString()}  ${text}\n` + el.textContent;
      if (msg.toLowerCase().includes('failed')) toast(msg, 'error');
      else if (msg.toLowerCase().includes('complete') || msg.toLowerCase().includes('approved') || msg.toLowerCase().includes('created')) toast(msg, 'success');
    }

    async function api(path, options = {}) {
      const res = await fetch(path, {
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
        ...options,
      });
      const contentType = res.headers.get('content-type') || '';
      const body = contentType.includes('application/json') ? await res.json() : await res.text();
      if (!res.ok) {
        throw new Error(typeof body === 'string' ? body : JSON.stringify(body));
      }
      return body;
    }

    async function fetchUsers() {
      const deals = await api('/api/deals');
      if (deals.items.length === 0) return;
      // fallback path: if users not directly available from API, keep nulls and prompt to run init scripts.
    }

    async function loadUsersDirectory() {
      const data = await api('/api/users');
      usersDirectory = data.items || [];
      usersById = {};
      usersByName = {};
      for (const user of usersDirectory) {
        const userId = String(user?.id || '').trim();
        if (userId) usersById[userId] = user;
        const nameKey = normalizeIdentityKey(user?.name || user?.full_name || '');
        if (nameKey && !usersByName[nameKey]) usersByName[nameKey] = user;
      }
      populateViewAsUsers();
      populateUserQuickFilter();
    }

    function populateViewAsUsers() {
      const select = document.getElementById('roleMode');
      if (!select) return;
      const previous = String(select.value || currentActorId || '').trim();
      const options = (usersDirectory || []).map(user => {
        const selected = previous && previous === user.id ? 'selected' : '';
        return `<option value='${user.id}' ${selected}>${user.name || user.email || user.id}</option>`;
      });
      select.innerHTML = options.join('');
      if (!select.value && options.length) {
        const preferred = (usersDirectory || []).find(u => effectiveRoleForUser(u) === 'cm') || usersDirectory[0];
        if (preferred) select.value = preferred.id;
      }
    }

    async function initDealForm() {
      const publicationSelect = document.getElementById('dealPublication');
      const pubs = await api('/api/publications');
      publicationSelect.innerHTML = pubs.items.map(p => `<option value="${p.name}">${publicationLabel(p.name)}</option>`).join('');

      const today = isoDate(new Date());
      document.getElementById('dealSowStart').value = today;

      const lines = document.getElementById('productLines');
      lines.innerHTML = '';
      productLineCount = 0;
      addProductLine();
      recomputeDealEndDate();
    }

    function productLineTemplate(index) {
      return `
        <div class='line-item' data-line='${index}'>
          <div class='field inline-field'>
            <label>Product</label>
            <select data-field='product_type' onchange='onProductLineTypeChange(${index})'>
              ${PRODUCT_TYPES.map(v => `<option value="${v}">${v}</option>`).join('')}
            </select>
          </div>
          <div class='field inline-field'>
            <label>Tier</label>
            <select data-field='tier'>
              ${PRODUCT_TIERS.map(v => `<option value="${v}">${v}</option>`).join('')}
            </select>
          </div>
          <div class='field inline-field line-demand' data-line-demand='${index}'>
            <label>Modules</label>
            <select data-field='demand_module_mode' onchange='onDemandModuleModeChange(${index})'>
              <option value='create_only' selected>Create only</option>
              <option value='create_reach'>Create + Reach</option>
              <option value='create_reach_capture'>Create + Reach + Capture</option>
            </select>
          </div>
          <div class='field line-demand line-demand-reach' data-line-demand='${index}'>
            <label>Reach Level</label>
            <select data-field='reach_level'>
              ${PRODUCT_TIERS.map(v => `<option value="${v}">${v}</option>`).join('')}
            </select>
          </div>
          <div class='field line-demand line-demand-capture' data-line-demand='${index}'>
            <label>Capture Level</label>
            <select data-field='capture_level'>
              ${PRODUCT_TIERS.map(v => `<option value="${v}">${v}</option>`).join('')}
            </select>
          </div>
          <div class='field line-response hidden' data-line-response='${index}'>
            <label>Lead volume</label>
            <input type='number' min='1' step='1' data-field='lead_volume' placeholder='e.g. 500' />
          </div>
          <button type='button' onclick='removeProductLine(${index})'>Remove</button>
        </div>
      `;
    }

    function addProductLine() {
      const lines = document.getElementById('productLines');
      productLineCount += 1;
      lines.insertAdjacentHTML('beforeend', productLineTemplate(productLineCount));
      onProductLineTypeChange(productLineCount);
      recomputeDealEndDate();
    }

    function removeProductLine(index) {
      const lines = document.getElementById('productLines');
      const items = lines.querySelectorAll('.line-item');
      if (items.length <= 1) {
        toast('At least one product line is required', 'error');
        return;
      }
      const target = lines.querySelector(`.line-item[data-line="${index}"]`);
      if (target) target.remove();
      recomputeDealEndDate();
    }

    function onProductLineTypeChange(index) {
      const row = document.querySelector(`#productLines .line-item[data-line="${index}"]`);
      if (!row) return;
      const type = row.querySelector('[data-field="product_type"]').value;
      row.querySelectorAll(`[data-line-demand="${index}"]`).forEach(el => el.classList.toggle('hidden', type !== 'demand'));
      row.querySelectorAll(`[data-line-response="${index}"]`).forEach(el => el.classList.toggle('hidden', type !== 'response'));
      if (type === 'demand') {
        onDemandModuleModeChange(index);
      }
      recomputeDealEndDate();
    }

    function onDemandModuleModeChange(index) {
      const row = document.querySelector(`#productLines .line-item[data-line="${index}"]`);
      if (!row) return;
      const mode = row.querySelector('[data-field="demand_module_mode"]')?.value || 'create_only';
      const reachWrap = row.querySelector('.line-demand-reach');
      const captureWrap = row.querySelector('.line-demand-capture');
      const reachSelect = row.querySelector('[data-field="reach_level"]');
      const captureSelect = row.querySelector('[data-field="capture_level"]');

      const showReach = mode === 'create_reach' || mode === 'create_reach_capture';
      const showCapture = mode === 'create_reach_capture';

      if (reachWrap) reachWrap.classList.toggle('hidden', !showReach);
      if (captureWrap) captureWrap.classList.toggle('hidden', !showCapture);
      if (reachSelect) {
        reachSelect.disabled = !showReach;
        reachSelect.required = showReach;
      }
      if (captureSelect) {
        captureSelect.disabled = !showCapture;
        captureSelect.required = showCapture;
      }
    }

    function addCalendarMonths(isoDate, months) {
      if (!isoDate) return null;
      const m = String(isoDate).match(/^(\d{4})-(\d{2})-(\d{2})$/);
      if (!m) return null;
      const year = Number(m[1]);
      const month = Number(m[2]);
      const day = Number(m[3]);
      const totalMonths = (year * 12) + (month - 1) + months;
      const targetYear = Math.floor(totalMonths / 12);
      const targetMonth = (totalMonths % 12) + 1;
      const lastDay = new Date(targetYear, targetMonth, 0).getDate();
      const targetDay = Math.min(day, lastDay);
      const yy = String(targetYear).padStart(4, '0');
      const mm = String(targetMonth).padStart(2, '0');
      const dd = String(targetDay).padStart(2, '0');
      return `${yy}-${mm}-${dd}`;
    }

    function addIsoDays(isoDate, days) {
      if (!isoDate) return null;
      const m = String(isoDate).match(/^(\d{4})-(\d{2})-(\d{2})$/);
      if (!m) return null;
      const year = Number(m[1]);
      const month = Number(m[2]);
      const day = Number(m[3]);
      const dt = new Date(Date.UTC(year, month - 1, day));
      dt.setUTCDate(dt.getUTCDate() + Number(days || 0));
      const yy = String(dt.getUTCFullYear()).padStart(4, '0');
      const mm = String(dt.getUTCMonth() + 1).padStart(2, '0');
      const dd = String(dt.getUTCDate()).padStart(2, '0');
      return `${yy}-${mm}-${dd}`;
    }

    function dealDurationMonthsFromLines() {
      const rows = [...document.querySelectorAll('#productLines .line-item')];
      const productTypes = rows
        .map(row => row.querySelector('[data-field="product_type"]')?.value || '')
        .filter(Boolean);
      if (productTypes.includes('demand')) return 12;
      if (productTypes.includes('response') || productTypes.includes('amplify')) return 3;
      return 3;
    }

    function recomputeDealEndDate() {
      const startEl = document.getElementById('dealSowStart');
      const endEl = document.getElementById('dealSowEnd');
      if (!startEl || !endEl) return;
      const startDate = startEl.value;
      if (!startDate) return;
      const months = dealDurationMonthsFromLines();
      const boundary = addCalendarMonths(startDate, months);
      if (!boundary) return;
      const computed = months === 3 ? addIsoDays(boundary, -1) : boundary;
      if (computed) endEl.value = computed;
    }

    function collectProductLines() {
      return [...document.querySelectorAll('#productLines .line-item')].map(row => {
        const productType = row.querySelector('[data-field="product_type"]').value;
        const tier = row.querySelector('[data-field="tier"]').value;
        const demandModuleMode = row.querySelector('[data-field="demand_module_mode"]')?.value || null;
        const reachLevel = row.querySelector('[data-field="reach_level"]')?.value || null;
        const captureLevel = row.querySelector('[data-field="capture_level"]')?.value || null;
        const leadRaw = row.querySelector('[data-field="lead_volume"]')?.value;
        const leadVolume = leadRaw ? Number(leadRaw) : null;
        if (productType === 'response' && (!leadVolume || leadVolume < 1)) {
          throw new Error('Response product lines require a positive lead volume.');
        }
        return {
          product_type: productType,
          tier,
          demand_module_mode: productType === 'demand' ? demandModuleMode : null,
          reach_level: productType === 'demand' ? reachLevel : null,
          capture_level: productType === 'demand' ? captureLevel : null,
          lead_volume: productType === 'response' ? leadVolume : null,
          options_json: {},
        };
      });
    }

    function collectContacts() {
      const name = document.getElementById('contactName').value.trim();
      const email = document.getElementById('contactEmail').value.trim();
      if (!name && !email) return [];
      if (!name || !email) throw new Error('Client contact requires both name and email.');
      return [{ name, email, title: null }];
    }

    function collectAttachments() {
      const fileName = document.getElementById('dealAttachment').value.trim();
      if (!fileName) return [];
      const safeName = fileName.replaceAll(' ', '_');
      return [{ file_name: fileName, storage_key: `intake/${Date.now()}_${safeName}` }];
    }

    function kpiCard(label, value, meta = '') {
      return `<article class='card kpi-card'><div class='kpi-label'>${label}</div><div class='kpi'>${value}</div>${meta ? `<div class='kpi-meta'>${meta}</div>` : ''}</article>`;
    }

    function escapeHtml(raw) {
      return String(raw || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function escapeHtmlMultiline(raw) {
      return escapeHtml(raw).replace(/\\n/g, '<br />');
    }

    function toTitle(raw) {
      return String(raw || '')
        .replace(/_/g, ' ')
        .trim()
        .replace(/\\b\\w/g, ch => ch.toUpperCase());
    }

    function formatStageLabel(raw, fallback = '-') {
      const value = String(raw ?? '').trim();
      if (!value) return fallback;
      const normalized = value
        .replace(/[\s-]+/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_+|_+$/g, '')
        .toLowerCase();
      return normalized ? toTitle(normalized) : fallback;
    }

    function scopeModuleCard(scope, opts = {}) {
      const s = scope || {};
      const scopeObjId = s.id || '';
      const panelMode = !!opts.panel;
      const editMode = (panelMode || !opts.popover) && isModuleEditing('scope', scopeObjId);
      const scopeStatus = String(s.status || '').toLowerCase();
      const scopeHealth = s.health || 'not_started';
      const am = s.am_user || {};
      const amInitials = am.initials || initialsFromName(am.name || '');
      const products = Array.isArray(s.product_lines) ? s.product_lines : [];
      const productsText = products.length
        ? products.map(p => `${toTitle(p.product_type || '-')}${p.tier ? ` ${toTitle(p.tier)}` : ''}`).join(' · ')
        : '-';
      const timeframe = `${s.sow_start_date ? niceDate(s.sow_start_date) : '-'} → ${s.sow_end_date ? niceDate(s.sow_end_date) : '-'}`;
      const campaigns = Array.isArray(s.campaigns) ? s.campaigns : [];
      const firstAttachment = Array.isArray(s.attachments) && s.attachments.length ? s.attachments[0] : null;
      const attachmentHref = firstAttachment
        ? (/^https?:\/\//i.test(String(firstAttachment.storage_key || ''))
            ? String(firstAttachment.storage_key)
            : `/${String(firstAttachment.storage_key || '').replace(/^\/+/, '')}`)
        : '';
      const campaignsAccordion = `
        <details class='ops-accordion surface-2'>
          <summary>Campaigns · ${campaigns.length}</summary>
          <div style='padding:8px 10px; display:grid; gap:8px;'>
            ${campaigns.map(c => campaignModuleCard(c, { idPrefix: `scope_${s.id || 'scope'}`, collapsed: true })).join('') || "<div class='sub'>No campaigns linked.</div>"}
          </div>
        </details>
      `;
      const icpAccordion = `
        <details class='ops-accordion surface-2'>
          <summary>ICP Details</summary>
          <div style='padding:8px 10px;' class='sub'>${escapeHtmlMultiline(s.icp || '-')}</div>
        </details>
      `;
      const objectiveAccordion = `
        <details class='ops-accordion surface-2'>
          <summary>Campaign Objective</summary>
          <div style='padding:8px 10px;' class='sub'>${escapeHtmlMultiline(s.campaign_objective || '-')}</div>
        </details>
      `;
      const messagingAccordion = `
        <details class='ops-accordion surface-2'>
          <summary>Messaging/Positioning</summary>
          <div style='padding:8px 10px;' class='sub'>${escapeHtmlMultiline(s.messaging_positioning || '-')}</div>
        </details>
      `;
      const showApproveButton = canApproveScopes() && ['submitted', 'readiness_failed', 'ops_approved', 'draft'].includes(scopeStatus);
      const showGenerateButton = canGenerateScopeCampaigns() && scopeStatus === 'readiness_passed';
      const scopeActionRow = (showApproveButton || showGenerateButton)
        ? `
          <div class='module-row span-2'>
            <span>Actions:</span>
            <div class='actions' style='margin-top:0;'>
              ${showApproveButton ? `<button onclick="approveScope('${s.id || ''}')">Approve Scope</button>` : ''}
              ${showGenerateButton ? `<button class='primary' onclick="generateCampaignsForScope('${s.id || ''}')">Generate Campaigns</button>` : ''}
            </div>
          </div>
        `
        : '';
      const subtitle = cardSlotEnabled('scope', 'subtitle') ? `${products.length} product${products.length === 1 ? '' : 's'}` : '';
      const statusNormalized = normalizeStatusValue(s.status || 'not_started');
      const amAvatar = [{ initials: amInitials || '--', name: am.name || '' }];
      const openButton = moduleOpenButtonHtml(opts);
      const showBrandName = cardSlotEnabled('scope', 'brand_name');
      const showScopeId = cardSlotEnabled('scope', 'scope_id');
      const showScopeStatus = cardSlotEnabled('scope', 'scope_status');
      const showScopeHealth = cardSlotEnabled('scope', 'scope_health');
      const showTimeframe = cardSlotEnabled('scope', 'timeframe');
      const showAmOwner = cardSlotEnabled('scope', 'am_owner');
      const showClientContact = cardSlotEnabled('scope', 'client_contact');
      const showProducts = cardSlotEnabled('scope', 'products');
      const showSowAttachment = cardSlotEnabled('scope', 'sow_attachment');
      const showCampaigns = cardSlotEnabled('scope', 'list') && cardSlotEnabled('scope', 'campaigns');
      const showIcp = cardSlotEnabled('scope', 'list') && cardSlotEnabled('scope', 'icp');
      const showObjective = cardSlotEnabled('scope', 'list') && cardSlotEnabled('scope', 'objective');
      const showMessaging = cardSlotEnabled('scope', 'list') && cardSlotEnabled('scope', 'messaging');
      const scopeProgress = deriveScopeCampaignProgress(s);
      const footer = moduleFooterHtml('scope', {
        statusHtml: statusChip(statusNormalized),
        avatarsHtml: moduleAvatarStack(amAvatar),
        dueText: s.sow_end_date ? `Due ${niceDate(s.sow_end_date)}` : '',
        actionsHtml: openButton || '',
      });
      const contactName = panelDetailValueText(s.client_contact_name || '-', '-');
      const contactEmail = String(s.client_contact_email || '').trim();
      const canEditScopeDetails = panelMode
        && editMode
        && (
          canUseControl('create_deal', currentRole)
          || canUseControl('ops_approve_latest_deal', currentRole)
          || canUseControl('manage_campaign_assignments', currentRole)
        );
      const clientNameInputId = `panelScopeClientName_${scopeObjId || 'scope'}`;
      const contactNameInputId = `panelScopeContactName_${scopeObjId || 'scope'}`;
      const contactEmailInputId = `panelScopeContactEmail_${scopeObjId || 'scope'}`;
      const panelDetailsHtml = panelMode
        ? panelDetailsSection([
            {
              label: 'Client',
              valueHtml: canEditScopeDetails
                ? `<input id='${clientNameInputId}' type='text' value='${escapeHtml(String(s.client_name || ''))}' />`
                : `<span>${escapeHtml(panelDetailValueText(s.client_name || '-', '-'))}</span>`,
            },
            { label: 'AM (Owner)', valueHtml: `${userPill(amInitials || '--', true, am.name || null, { userId: am.user_id || s.am_user_id || '', roleKey: 'am' })}<span>${escapeHtml(panelDetailValueText(am.name || '-', '-'))}</span>` },
            {
              label: 'Contact Name',
              valueHtml: canEditScopeDetails
                ? `<input id='${contactNameInputId}' type='text' value='${escapeHtml(String(s.client_contact_name || ''))}' />`
                : `<span>${escapeHtml(contactName)}</span>`,
            },
            {
              label: 'Contact Email',
              valueHtml: canEditScopeDetails
                ? `<input id='${contactEmailInputId}' type='email' value='${escapeHtml(contactEmail)}' />`
                : (contactEmail
                  ? `<a href='mailto:${escapeHtml(contactEmail)}'>${escapeHtml(contactEmail)}</a>`
                  : `<span>-</span>`),
            },
            { label: 'Timeframe', valueHtml: `<span>${escapeHtml(panelTimeframeText(s.sow_start_date, s.sow_end_date))}</span>` },
            { label: 'Status', valueHtml: statusChip(statusNormalized) },
          ])
        : '';
      return `
        <details class='module-card${editMode ? ' is-editing' : ''}' data-module='scope' data-obj-type='scope' data-obj-id='${s.id || ''}' data-campaign-id='' data-editing='${editMode ? '1' : '0'}'>
          <summary class='module-head'>
            <div class='module-head-left'>
              <span class='module-chevron'>▸</span>
              <span class='module-icon'>${moduleIcon('scope')}</span>
              <div class='module-title-block'>
                <div class='module-title'>${s.client_name || '-'}</div>
                ${subtitle ? `<div class='module-subtitle'>${subtitle}</div>` : ''}
              </div>
              <div class='module-summary-inline module-summary-grid scope-summary-grid'>
                <span class='summary-pill-slot slot-status' data-slot='status'>${statusChip(s.status || 'not_started')}</span>
                <span class='summary-pill-slot slot-health' data-slot='health'>${healthChip(scopeHealth)}</span>
                <span class='module-summary-text summary-secondary summary-slot slot-timeframe_start' data-slot='timeframe_start'>${s.sow_start_date ? `${niceDate(s.sow_start_date)} →` : ''}</span>
                <span class='module-summary-text summary-secondary summary-slot slot-timeframe_end' data-slot='timeframe_end'>${s.sow_end_date ? niceDate(s.sow_end_date) : '-'}</span>
                <span class='module-summary-right scope-id summary-slot slot-campaign_id' data-slot='campaign_id'>${s.id || '-'}</span>
              </div>
            </div>
            <div class='module-head-right'>${moduleHeadRight('scope', s.id || '', opts)}</div>
          </summary>
          <div class='module-fields module-body'>
            ${panelDetailsHtml}
            ${panelMode ? '' : `
            ${cardSlotEnabled('scope', 'progress') ? `
              <div class='card-progress span-2'>
                <div class='progress-meta'><span class='progress-label'>Overall progress</span><span class='progress-pct'>${scopeProgress.pct}%</span></div>
                ${scopeProgress.barHtml}
              </div>
            ` : ''}
            ${cardSlotEnabled('scope', 'key_values') ? `
            ${(showBrandName || showScopeId) ? `
            <div class='module-row'>
              ${showBrandName ? `<span>Brand name:</span><span>${s.client_name || '-'}</span>` : ''}
              ${showScopeId ? `<span>Scope ID:</span><span><code>${s.id || '-'}</code></span>` : ''}
            </div>` : ''}
            ${(showScopeStatus || showScopeHealth || showTimeframe) ? `
            <div class='module-row'>
              ${showScopeStatus ? `<span>Scope status:</span>${statusChip(s.status || 'not_started')}` : ''}
              ${showScopeHealth ? `<span>Scope health:</span>${healthChip(scopeHealth)}` : ''}
              ${showTimeframe ? `<span>Timeframe:</span><span>${timeframe}</span>` : ''}
            </div>` : ''}
            ${(showAmOwner || showClientContact) ? `
            <div class='module-row'>
              ${showAmOwner ? `<span>AM:</span>${userPill(amInitials || '--', true, am.name || null, { userId: am.user_id || s.am_user_id || '', roleKey: 'am' })}<span>${am.name || '-'}</span>` : ''}
              ${showClientContact ? `<span>Client contact:</span><span>${s.client_contact_name || '-'}</span>` : ''}
            </div>` : ''}
            ${showProducts ? `<div class='module-row span-2'><span>Products:</span><span>${productsText}</span></div>` : ''}
            ${showSowAttachment ? `<div class='module-row span-2'>
              <span>SOW attachment:</span>
              ${firstAttachment
                ? `<a href='${attachmentHref}' target='_blank' rel='noopener noreferrer'>${escapeHtml(firstAttachment.file_name || 'Open attachment')}</a>`
                : `<span>No attachment</span>`
              }
            </div>` : ''}
            ` : ''}
            ${cardSlotEnabled('scope', 'tags') ? `<div class='module-row span-2'><span>Tags:</span><div class='card-tags'>${products.map(p => `<span class='tag'>${toTitle(p.product_type || '-')}</span>`).join('') || "<span class='tag'>None</span>"}</div></div>` : ''}
            ${cardSlotEnabled('scope', 'actions') ? scopeActionRow : ''}
            ${showCampaigns ? `<div class='module-row span-2' style='display:block;'>${campaignsAccordion}</div>` : ''}
            ${showIcp ? `<div class='module-row span-2' style='display:block;'>${icpAccordion}</div>` : ''}
            ${showObjective ? `<div class='module-row span-2' style='display:block;'>${objectiveAccordion}</div>` : ''}
            ${showMessaging ? `<div class='module-row span-2' style='display:block;'>${messagingAccordion}</div>` : ''}
            `}
          </div>
          ${footer}
        </details>
      `;
    }

    async function renderSummary() {
      const s = await api('/api/dashboard/summary');
      document.getElementById('kpis').innerHTML = [
        kpiCard('Active Campaigns', s.campaigns_total, 'live pipeline'),
        kpiCard('At Risk', s.open_system_risks, 'system flags'),
        kpiCard('Team Capacity', s.over_capacity_rows, 'rows over weekly cap'),
        kpiCard('On Track', s.ready_to_publish, 'ready to publish'),
        kpiCard('Scopes', s.deals_total, `${s.deals_readiness_passed} readiness passed`),
        kpiCard('Deliverables', s.deliverables_total, `${s.awaiting_client_review} in client review`),
        kpiCard('Open Steps', s.workflow_steps_open, `${s.workflow_steps_due_tracked} with due dates`),
        kpiCard('Open Escalations', s.open_escalations, 'needs leadership visibility'),
      ].join('');
    }

    function rowKeyFor(moduleType, id) {
      return `${String(moduleType || '').toLowerCase()}:${String(id || '')}`;
    }

    function buildScopeListRows(scopes = [], workspaceMap = {}) {
      return (scopes || []).map(scope => {
        const campaigns = Array.isArray(scope?.campaigns) ? scope.campaigns : [];
        const campaignStatuses = campaigns.map(c => normalizeStatusValue(c?.status || 'not_started'));
        const scopeAm = scope?.am_user || {};
        const ownerUserId = String(scopeAm?.user_id || scope?.am_user_id || '').trim();
        const ownerName = String(scopeAm?.name || scope?.am_name || '').trim();
        const ownerInitials = String(
          scopeAm?.initials
          || scope?.am_initials
          || (ownerName ? initialsFromName(ownerName) : '--')
        ).trim() || '--';
        const campaignRows = buildCampaignRows(campaigns, workspaceMap).map(row => ({
          ...row,
          scope_id: scope.id || row.scope_id || '',
          context_id: scope.id || row.context_id || '',
        }));
        return {
          row_key: rowKeyFor('scope', scope.id),
          module_type: 'scope',
          id: scope.id,
          title: scope.client_name || scope.brand_name || scope.id || 'Scope',
          status: normalizeStatusValue(scope.status || 'not_started'),
          health: String(scope.health || 'not_started').toLowerCase(),
          owner_initials: ownerInitials,
          owner_name: ownerName,
          owner_user_id: ownerUserId,
          participants: ownerUserId ? [{ id: ownerUserId, initials: ownerInitials, name: ownerName }] : [],
          progress_statuses: campaignStatuses,
          context_id: '',
          children: campaignRows,
        };
      });
    }

    function buildCampaignRows(campaignItems = [], workspaceMap = {}) {
      const stageKey = (value) => String(value || '').toLowerCase().trim().replace(/[\s-]+/g, '_');
      return (campaignItems || []).map(campaign => {
        const ws = workspaceMap[campaign.id] || {};
        const campaignAssignedUsers = Array.isArray(campaign?.assigned_users) ? campaign.assigned_users : [];
        const campaignOwner = campaignAssignedUsers.find(u => String(u?.role || '').toLowerCase().trim() === 'cm') || null;
        const campaignOwnerName = String(campaignOwner?.name || '').trim();
        const campaignOwnerInitials = String(campaignOwner?.initials || initialsFromName(campaignOwnerName || '') || '--').trim() || '--';
        const campaignOwnerUserId = String(campaignOwner?.user_id || campaignOwner?.id || '').trim();
        const stages = Array.isArray(ws.stages) ? ws.stages : [];
        const deliverables = Array.isArray(ws.deliverables?.items) ? ws.deliverables.items : [];
        const steps = Array.isArray(ws.workflow_steps?.items) ? ws.workflow_steps.items : [];
        const stageRows = stages.map(stage => {
          const stageNameKey = stageKey(stage?.name || '');
          const stageId = String(stage?.id || '').trim();
          const stageDisplayId = String(stage?.display_id || '').trim();
          const stageSteps = steps.filter(step => {
            const stepStageKey = stageKey(step?.stage_name || step?.stage || step?.deliverable_stage || '');
            const stepStageId = String(step?.stage_id || '').trim();
            return (
              (stageNameKey && stepStageKey && stepStageKey === stageNameKey) ||
              (stageId && stepStageId === stageId) ||
              (stageDisplayId && stepStageId === stageDisplayId)
            );
          });
          if (!stageSteps.length) {
            return null;
          }
          const stageWindow = deriveStageWindowBounds(stageSteps);
          return {
            row_key: rowKeyFor('stage', stage.id),
            module_type: 'stage',
            id: stage.id,
            title: formatStageLabel(stage.name || 'Stage', 'Stage'),
            status: normalizeStatusValue(stage.status || deriveStageStatus(stageSteps)),
            health: String(stage.health || deriveStageHealth(stageSteps) || 'not_started').toLowerCase(),
            timeframe_start: stage?.current_start || stage?.baseline_start || stageWindow.start || null,
            timeframe_due: stage?.current_due || stage?.baseline_due || stageWindow.end || null,
            owner_initials: '--',
            owner_name: '',
            owner_user_id: '',
            participants: [],
            campaign_id: campaign.id,
            context_id: campaign.id,
            progress_statuses: stageSteps.map(s => normalizeStatusValue(s.status || s.step_state || 'not_started')),
            children: stageSteps.map(step => ({
              row_key: rowKeyFor('step', step.id),
              module_type: 'step',
              id: step.id,
              title: step.name || step.id || 'Step',
              status: normalizeStatusValue(step.status || step.step_state || 'not_started'),
              health: String(step.health || 'not_started').toLowerCase(),
              timeframe_start: step?.current_start || step?.timeframe_start || null,
              timeframe_due: step?.current_due || step?.timeframe_due || null,
              owner_initials: step.owner_initials || '--',
              owner_name: step.owner_name || step.owner_user_name || '',
              owner_user_id: step.next_owner_user_id || '',
              participants: [{ id: step.next_owner_user_id || '', initials: step.owner_initials || '--', name: step.owner_name || step.owner_user_name || '' }],
              campaign_id: campaign.id,
              context_id: campaign.id,
              progress_statuses: [],
              children: [],
            })),
          };
        }).filter(Boolean);
        const deliverableRows = deliverables.map(deliverable => ({
          row_key: rowKeyFor('deliverable', deliverable.id),
          module_type: 'deliverable',
          id: deliverable.id,
          title: deliverable.title || deliverable.id || 'Deliverable',
          status: normalizeStatusValue(deliverable.status || 'not_started'),
          delivery_status: String(deliverable.delivery_status || deliverableRawStatusFromGlobal(deliverable.status || 'not_started')).toLowerCase(),
          health: '',
          timeframe_start: deliverable?.current_start || deliverable?.timeframe_start || null,
          timeframe_due: deliverable?.current_due || deliverable?.timeframe_due || null,
          owner_initials: deliverable.owner_initials || '--',
          owner_name: deliverable.owner_name || '',
          owner_user_id: deliverable.owner_user_id || '',
          participants: [{ id: deliverable.owner_user_id || '', initials: deliverable.owner_initials || '--', name: deliverable.owner_name || '' }],
          campaign_id: campaign.id,
          context_id: campaign.id,
          progress_statuses: [],
          children: [],
        }));
        return {
          row_key: rowKeyFor('campaign', campaign.id),
          module_type: 'campaign',
          id: campaign.id,
          title: campaign.title || campaign.id || 'Campaign',
          status: normalizeStatusValue(campaign.status || 'not_started'),
          health: String(campaign.health || campaign.campaign_health || 'not_started').toLowerCase(),
          timeframe_start: campaign?.timeframe_start || ws?.campaign?.timeframe_start || null,
          timeframe_due: campaign?.timeframe_due || ws?.campaign?.timeframe_due || null,
          owner_initials: campaignOwnerInitials,
          owner_name: campaignOwnerName,
          owner_user_id: campaignOwnerUserId,
          participants: campaignAssignedUsers.map(u => ({ id: u.user_id || u.id || '', role: u.role || '', initials: u.initials || '--', name: u.name || '' })),
          scope_id: campaign.scope_id || '',
          context_id: campaign.scope_id || '',
          progress_statuses: stages.map(s => normalizeStatusValue(s.status || 'not_started')),
          children: [...stageRows, ...deliverableRows],
        };
      });
    }

    function renderListModule(containerId, rows = []) {
      const body = document.getElementById(containerId);
      if (!body) return;
      body.innerHTML = `<div class='list-module'>${(rows || []).map(row => listRowHtml(row, 0)).join('') || "<div class='sub'>No items.</div>"}</div>`;
    }

    async function renderDeals() {
      const actorQ = currentActorId ? `?actor_user_id=${encodeURIComponent(currentActorId)}` : '';
      const data = await api(`/api/deals${actorQ}`);
      const productFilter = getFilterValue('qProducts') || 'all';
      const scopeHealthFilter = getFilterValue('qScopeHealth') || 'all';
      const selectedUserIds = selectedUserFilterSet();
      const items = data.items.filter(d => {
        if (!scopeMatchesUserFilter(d, selectedUserIds)) return false;
        const scopeHealth = String(d?.health || 'not_started').toLowerCase();
        if (scopeHealthFilter !== 'all' && scopeHealth !== scopeHealthFilter) return false;
        if (productFilter === 'all') return true;
        const lines = Array.isArray(d?.product_lines) ? d.product_lines : [];
        const campaigns = Array.isArray(d?.campaigns) ? d.campaigns : [];
        const matchLine = lines.some(line => String(line?.product_type || '').toLowerCase() === productFilter);
        const matchCampaign = campaigns.some(c => String(c?.type || '').toLowerCase() === productFilter);
        return matchLine || matchCampaign;
      });
      const allCampaigns = items.flatMap(scope => Array.isArray(scope?.campaigns) ? scope.campaigns : []);
      const workspaceEntries = await Promise.all(allCampaigns.map(async (campaign) => {
        const cid = String(campaign?.id || campaign?.campaign_id || '').trim();
        if (!cid) return [cid, null];
        try {
          const ws = await api(`/api/campaigns/${encodeURIComponent(cid)}/workspace`);
          return [cid, ws];
        } catch (_) {
          return [cid, null];
        }
      }));
      const workspaceMap = Object.fromEntries(workspaceEntries.filter(([k]) => !!k));
      const rows = buildScopeListRows(items, workspaceMap);
      LIST_ROWS_CACHE.deals = rows;
      renderListModule('dealsBody', rows);
      document.getElementById('dealsCount').textContent = `${items.length} shown / ${data.items.length} total`;
      return data.items;
    }

    function teamLabel(value) {
      const v = String(value || '').toLowerCase();
      if (v === 'client_services') return 'Client Services';
      if (v === 'sales') return 'Sales';
      if (v === 'editorial') return 'Editorial';
      if (v === 'marketing') return 'Marketing';
      return value || '-';
    }

    function seniorityLabel(value) {
      const v = String(value || '').toLowerCase();
      if (v === 'leadership') return 'Leadership';
      if (v === 'manager') return 'Manager';
      if (v === 'standard') return 'Standard';
      return value || '-';
    }

    function appRoleLabel(value) {
      const v = String(value || '').toLowerCase();
      if (v === 'superadmin') return 'Superadmin';
      if (v === 'admin') return 'Admin';
      if (v === 'user') return 'User';
      return value || '-';
    }

    function togglePeopleNameSort() {
      peopleSortDirection = peopleSortDirection === 'asc' ? 'desc' : 'asc';
      renderPeople().catch(err => log('People render failed', String(err)));
    }

    async function renderPeople() {
      const data = await api('/api/users');
      const teamFilter = getFilterValue('qPeopleTeam') || 'all';
      const seniorityFilter = getFilterValue('qPeopleSeniority') || 'all';
      const appRoleFilter = getFilterValue('qPeopleAppRole') || 'all';
      const items = (data.items || []).filter((u) => {
        const teamOk = teamFilter === 'all' || String(u.primary_team || '').toLowerCase() === teamFilter;
        const seniorityOk = seniorityFilter === 'all' || String(u.seniority || '').toLowerCase() === seniorityFilter;
        const appRoleOk = appRoleFilter === 'all' || String(u.app_role || '').toLowerCase() === appRoleFilter;
        return teamOk && seniorityOk && appRoleOk;
      });
      const sortedItems = [...items].sort((a, b) => {
        const an = String(a?.name || '').toLowerCase();
        const bn = String(b?.name || '').toLowerCase();
        const cmp = an.localeCompare(bn);
        return peopleSortDirection === 'desc' ? -cmp : cmp;
      });
      const body = document.getElementById('peopleBody');
      const count = document.getElementById('peopleCount');
      if (count) count.textContent = `${items.length} shown / ${(data.items || []).length} total`;
      if (!body) return items;
      const sortArrow = peopleSortDirection === 'asc' ? '↑' : '↓';
      body.innerHTML = `
        <table>
          <thead>
            <tr>
              <th><button type='button' class='ghost' onclick='togglePeopleNameSort()'>Name ${sortArrow}</button></th>
              <th>Email</th>
              <th>Team</th>
              <th>Seniority</th>
              <th>App Role</th>
            </tr>
          </thead>
          <tbody>
            ${sortedItems.map((u) => `
              <tr>
                <td><strong>${escapeHtml(u.name || '-')}</strong></td>
                <td>${escapeHtml(u.email || '-')}</td>
                <td><span class='tag'>${teamLabel(u.primary_team)}</span></td>
                <td><span class='tag'>${seniorityLabel(u.seniority)}</span></td>
                <td><span class='tag'>${appRoleLabel(u.app_role)}</span> <button type='button' class='ghost' onclick="openObjectPanelChild('user','${escapeHtml(String(u.id || ''))}','')">Details</button></td>
              </tr>
            `).join('') || "<tr><td colspan='5' class='sub'>No people match these filters.</td></tr>"}
          </tbody>
        </table>
      `;
      return sortedItems;
    }

    function campaignDeepLinkTargetFromUrl() {
      const qs = new URLSearchParams(window.location.search || '');
      const targetType = String(qs.get('targetType') || '').toLowerCase();
      const targetId = String(qs.get('targetId') || '').trim();
      const campaignId = String(qs.get('campaignId') || '').trim();
      const expand = String(qs.get('expand') || '').toLowerCase();
      if (!targetType || !targetId) return null;
      if (!['campaign', 'stage', 'deliverable', 'step'].includes(targetType)) return null;
      return {
        targetType,
        targetId,
        campaignId: campaignId || null,
        expand: ['work', 'deliverables'].includes(expand) ? expand : null,
      };
    }

    function attrEqSelector(attr, value) {
      const raw = String(value || '');
      const safe = (typeof CSS !== 'undefined' && typeof CSS.escape === 'function')
        ? CSS.escape(raw)
        : raw.replace(/"/g, '\\"');
      return `[${attr}="${safe}"]`;
    }

    function findCampaignAccordion(campaignCard, key) {
      if (!(campaignCard instanceof HTMLElement)) return null;
      const wanted = String(key || '').toLowerCase();
      const accordions = Array.from(campaignCard.querySelectorAll('.ops-accordion'));
      return accordions.find(acc => String(acc.querySelector(':scope > summary')?.textContent || '').trim().toLowerCase().startsWith(wanted)) || null;
    }

    function highlightModuleCard(card) {
      if (!(card instanceof HTMLElement)) return;
      card.classList.add('module-target-highlight');
      setTimeout(() => {
        card.classList.remove('module-target-highlight');
      }, 2200);
    }

    function revealCampaignTarget(target) {
      if (!target) return;
      const body = document.getElementById('campaignsBody');
      if (!body) return;

      const campaignId = target.campaignId || (target.targetType === 'campaign' ? target.targetId : null);
      if (!campaignId) return;

      const campaignSel = `.module-card[data-module='campaign']${attrEqSelector('data-obj-id', campaignId)}`;
      const campaignCard = body.querySelector(campaignSel);
      if (!(campaignCard instanceof HTMLDetailsElement)) {
        toast(`Target not found: campaign ${campaignId}`, 'error');
        body.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
      campaignCard.open = true;

      let targetCard = campaignCard;
      const expandKey = target.expand || (target.targetType === 'deliverable' ? 'deliverables' : (target.targetType === 'campaign' ? null : 'work'));
      const targetAccordion = expandKey ? findCampaignAccordion(campaignCard, expandKey) : null;
      if (targetAccordion instanceof HTMLDetailsElement) targetAccordion.open = true;

      if (target.targetType === 'deliverable') {
        const selector = `.module-card[data-module='deliverable']${attrEqSelector('data-obj-id', target.targetId)}`;
        const deliverableCard = campaignCard.querySelector(selector);
        if (deliverableCard instanceof HTMLDetailsElement) {
          deliverableCard.open = true;
          targetCard = deliverableCard;
        }
      } else if (target.targetType === 'stage') {
        const selector = `.module-card[data-module='stage']${attrEqSelector('data-obj-id', target.targetId)}`;
        const stageCard = campaignCard.querySelector(selector);
        if (stageCard instanceof HTMLDetailsElement) {
          stageCard.open = true;
          targetCard = stageCard;
        }
      } else if (target.targetType === 'step') {
        const selector = `.module-card[data-module='step']${attrEqSelector('data-obj-id', target.targetId)}`;
        const stepCard = campaignCard.querySelector(selector);
        if (stepCard instanceof HTMLDetailsElement) {
          const stageParent = stepCard.closest(".module-card[data-module='stage']");
          if (stageParent instanceof HTMLDetailsElement) stageParent.open = true;
          stepCard.open = true;
          targetCard = stepCard;
        }
      }

      targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      highlightModuleCard(targetCard);
      if (targetCard === campaignCard && target.targetType !== 'campaign') {
        toast(`Target ${target.targetType} not found in campaign ${campaignId}`, 'error');
      }
    }

    function revealListTarget(target) {
      if (!target) return;
      const body = document.getElementById('campaignsBody');
      if (!body) return;
      const targetType = String(target.targetType || '').toLowerCase();
      const targetId = String(target.targetId || '').trim();
      const selector = `.list-module-row[data-module='${targetType}'][data-object-id='${targetId}']`;
      const row = body.querySelector(selector);
      if (row instanceof HTMLElement) {
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        row.classList.add('module-target-highlight');
        setTimeout(() => row.classList.remove('module-target-highlight'), 2000);
      }
    }

    function toggleListRow(rowKey) {
      const key = String(rowKey || '').trim();
      if (!key) return;
      if (LIST_EXPANDED_ROW_KEYS.has(key)) LIST_EXPANDED_ROW_KEYS.delete(key);
      else LIST_EXPANDED_ROW_KEYS.add(key);
      const screen = String(currentScreen || '').toLowerCase();
      if (screen === 'campaigns' && Array.isArray(LIST_ROWS_CACHE.campaigns) && LIST_ROWS_CACHE.campaigns.length) {
        renderListModule('campaignsBody', LIST_ROWS_CACHE.campaigns);
        requestAnimationFrame(() => applyModuleLayoutRules(document.getElementById('campaignsBody') || document));
        return;
      }
      if ((screen === 'deals' || screen === 'scopes') && Array.isArray(LIST_ROWS_CACHE.deals) && LIST_ROWS_CACHE.deals.length) {
        renderListModule('dealsBody', LIST_ROWS_CACHE.deals);
        requestAnimationFrame(() => applyModuleLayoutRules(document.getElementById('dealsBody') || document));
        return;
      }
      renderScreen().catch(err => log('List row toggle failed', String(err)));
    }

    function listOpenPath(moduleType, objectId, campaignId = '') {
      const type = String(moduleType || '').toLowerCase();
      const id = String(objectId || '').trim();
      const cid = String(campaignId || '').trim();
      if (type === 'scope') return '/scopes';
      if (type === 'campaign') return campaignsPathWithTarget({ targetType: 'campaign', targetId: id, campaignId: id });
      if (type === 'stage') return campaignsPathWithTarget({ targetType: 'stage', targetId: id, campaignId: cid, expand: 'work' });
      if (type === 'deliverable') return campaignsPathWithTarget({ targetType: 'deliverable', targetId: id, campaignId: cid, expand: 'deliverables' });
      if (type === 'step') return campaignsPathWithTarget({ targetType: 'step', targetId: id, campaignId: cid, expand: 'work' });
      if (type === 'user') return '/people';
      return '/campaigns';
    }

    async function handleListMenuAction(action, moduleType, objectId, campaignId = '') {
      const act = String(action || '').toLowerCase();
      const type = String(moduleType || '').toLowerCase();
      const objId = String(objectId || '').trim();
      if (!act || !objId) return;
      if (act === 'open') {
        const row = document.querySelector(`.list-module-row[data-module='${type}'][data-object-id='${objId}']`);
        const encoded = String(row?.getAttribute('data-list-popover-payload') || '').trim();
        if (encoded) {
          openObjectPanelByEncoded(encoded);
          return;
        }
        const payload = await fetchObjectPanelPayload(type, objId, campaignId);
        if (payload) {
          openObjectPanelByPayload(payload);
        } else {
          const path = listOpenPath(type, objId, campaignId);
          if (path) window.location.href = path;
        }
        return;
      }
      if (act === 'edit') {
        await toggleModuleEditFromMenu(type, objId);
        return;
      }
      if (act === 'delete') {
        if (type === 'campaign') {
          await deleteCampaign(objId);
          return;
        }
        if (type === 'deliverable') {
          await deleteDeliverable(objId);
          return;
        }
      }
    }

    function normalizeAccordionSummaryText(text) {
      return String(text || '')
        .replace(/\s+/g, ' ')
        .trim()
        .toLowerCase()
        .slice(0, 120);
    }

    function accordionStateKey(el) {
      if (!(el instanceof HTMLElement)) return '';
      const summaryText = normalizeAccordionSummaryText(el.querySelector(':scope > summary')?.textContent || '');
      const campaignId = String(el.closest(".module-card[data-module='campaign']")?.getAttribute('data-obj-id') || '');
      const stageId = String(el.closest(".module-card[data-module='stage']")?.getAttribute('data-obj-id') || '');
      let idx = 0;
      const parent = el.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(ch => ch instanceof HTMLDetailsElement && ch.classList.contains('ops-accordion'));
        idx = Math.max(0, siblings.indexOf(el));
      }
      return `${campaignId}|${stageId}|${idx}|${summaryText}`;
    }

    function captureCampaignsViewState() {
      const body = document.getElementById('campaignsBody');
      if (!body) return null;
      const openModuleKeys = Array.from(body.querySelectorAll("details.module-card[open]"))
        .map(el => {
          const module = String(el.getAttribute('data-module') || '').trim();
          const objId = String(el.getAttribute('data-obj-id') || '').trim();
          return (module && objId) ? `${module}|${objId}` : '';
        })
        .filter(Boolean);
      const openCampaignIds = Array.from(body.querySelectorAll("details.module-card[data-module='campaign'][open]"))
        .map(el => String(el.getAttribute('data-obj-id') || ''))
        .filter(Boolean);
      const openAccordions = Array.from(body.querySelectorAll('details.ops-accordion[open]'))
        .map(accordionStateKey)
        .filter(Boolean);
      const focusedCard = document.activeElement instanceof HTMLElement
        ? document.activeElement.closest('details.module-card')
        : null;
      const focusTarget = focusedCard ? {
        module: String(focusedCard.getAttribute('data-module') || ''),
        objId: String(focusedCard.getAttribute('data-obj-id') || ''),
      } : null;
      return {
        scrollY: window.scrollY || 0,
        openModuleKeys,
        openCampaignIds,
        openAccordions,
        focusTarget,
      };
    }

    async function restoreCampaignsViewState(state) {
      if (!state) return;
      await new Promise(resolve => requestAnimationFrame(resolve));
      const body = document.getElementById('campaignsBody');
      if (!body) return;
      const openModuleSet = new Set(state.openModuleKeys || []);
      for (const campaignId of (state.openCampaignIds || [])) {
        const selector = `.module-card[data-module='campaign']${attrEqSelector('data-obj-id', campaignId)}`;
        const el = body.querySelector(selector);
        if (el instanceof HTMLDetailsElement) {
          el.open = true;
        }
      }
      if (openModuleSet.size) {
        for (const card of Array.from(body.querySelectorAll('details.module-card'))) {
          if (!(card instanceof HTMLDetailsElement)) continue;
          const module = String(card.getAttribute('data-module') || '').trim();
          const objId = String(card.getAttribute('data-obj-id') || '').trim();
          if (!module || !objId) continue;
          if (openModuleSet.has(`${module}|${objId}`)) card.open = true;
        }
      }
      const openSet = new Set(state.openAccordions || []);
      if (openSet.size) {
        for (const acc of Array.from(body.querySelectorAll('details.ops-accordion'))) {
          if (!(acc instanceof HTMLDetailsElement)) continue;
          const key = accordionStateKey(acc);
          if (openSet.has(key)) acc.open = true;
        }
      }

      let scrolled = false;
      if (state.focusTarget?.module && state.focusTarget?.objId) {
        const target = body.querySelector(`.module-card[data-module='${state.focusTarget.module}']${attrEqSelector('data-obj-id', state.focusTarget.objId)}`);
        if (target instanceof HTMLElement) {
          const parentCampaign = target.closest(".module-card[data-module='campaign']");
          if (parentCampaign instanceof HTMLDetailsElement) parentCampaign.open = true;
          const parentAccordions = Array.from(target.closest('.module-fields')?.querySelectorAll('details.ops-accordion') || []);
          for (const acc of parentAccordions) {
            if (acc instanceof HTMLDetailsElement) acc.open = true;
          }
          const stageParent = target.closest(".module-card[data-module='stage']");
          if (stageParent instanceof HTMLDetailsElement) stageParent.open = true;
          target.scrollIntoView({ behavior: 'auto', block: 'center' });
          scrolled = true;
        }
      }
      if (!scrolled) window.scrollTo(0, Math.max(0, Number(state.scrollY || 0)));
      requestAnimationFrame(() => applyModuleLayoutRules());
    }

    async function runCampaignAwareRefresh(refreshFn) {
      const campaignsState = currentScreen === 'campaigns' ? captureCampaignsViewState() : null;
      await refreshFn();
      await restoreCampaignsViewState(campaignsState);
    }

    async function renderCampaigns() {
      const actorQ = currentActorId ? `?actor_user_id=${encodeURIComponent(currentActorId)}` : '';
      const data = await api(`/api/campaigns${actorQ}`);
      campaignHealthByCampaignId = {};
      for (const item of (data.items || [])) {
        campaignHealthByCampaignId[item.id] = {
          campaign_id: item.id,
          overall_status: item.health || item.campaign_health || 'not_started',
          worst_signal: null,
          next_action: null,
        };
      }
      const deepTarget = campaignDeepLinkTargetFromUrl();
      let statusFilter = getFilterValue('qCampaigns');
      const productFilter = getFilterValue('qProducts') || 'all';
      const campaignHealthFilter = getFilterValue('qCampaignHealth') || 'all';
      const selectedUserIds = selectedUserFilterSet();
      if (deepTarget && statusFilter !== 'all') {
        if (campaignFilterBeforeForceReveal == null) campaignFilterBeforeForceReveal = statusFilter;
        const filterEl = document.getElementById('qCampaigns');
        if (filterEl) filterEl.value = 'all';
        statusFilter = 'all';
      }
      const items = data.items.filter(c => {
        if (!campaignMatchesUserFilter(c, selectedUserIds)) return false;
        const statusOk = statusFilter === 'all' || String(c.status || '').toLowerCase() === statusFilter;
        if (!statusOk) return false;
        const healthOk = campaignHealthFilter === 'all' || String(c.health || c.campaign_health || 'not_started').toLowerCase() === campaignHealthFilter;
        if (!healthOk) return false;
        if (productFilter === 'all') return true;
        return String(c.type || '').toLowerCase() === productFilter;
      });
      const workspaceEntries = await Promise.all(items.map(async (campaign) => {
        try {
          const ws = await api(`/api/campaigns/${encodeURIComponent(campaign.id)}/workspace`);
          return [campaign.id, ws];
        } catch (_) {
          return [campaign.id, null];
        }
      }));
      const workspaceMap = Object.fromEntries(workspaceEntries);
      if (deepTarget) {
        const deepType = String(deepTarget.targetType || '').toLowerCase();
        const deepTargetId = String(deepTarget.targetId || '').trim();
        const deepCampaignId = String(deepTarget.campaignId || (deepType === 'campaign' ? deepTargetId : '')).trim();
        if (deepCampaignId) LIST_EXPANDED_ROW_KEYS.add(rowKeyFor('campaign', deepCampaignId));
        if (deepType === 'stage' && deepTargetId) {
          LIST_EXPANDED_ROW_KEYS.add(rowKeyFor('stage', deepTargetId));
        }
        if (deepType === 'step' && deepTargetId && deepCampaignId) {
          const ws = workspaceMap[deepCampaignId];
          const wsSteps = Array.isArray(ws?.workflow_steps?.items) ? ws.workflow_steps.items : [];
          const matched = wsSteps.find(s => String(s?.id || '').trim() === deepTargetId);
          const stageId = String(matched?.stage_id || '').trim();
          if (stageId) LIST_EXPANDED_ROW_KEYS.add(rowKeyFor('stage', stageId));
        }
      }
      const rows = buildCampaignRows(items, workspaceMap);
      LIST_ROWS_CACHE.campaigns = rows;
      renderListModule('campaignsBody', rows);
      document.getElementById('campaignsCount').textContent = `${items.length} shown / ${data.items.length} total`;

      const select = document.getElementById('workspaceCampaignSelect');
      if (select) {
        select.innerHTML = data.items.map(c => `<option value="${c.id}">${c.id} · ${c.title}</option>`).join('') || `<option value="">No campaigns</option>`;
        if (!currentWorkspaceCampaignId && data.items.length) currentWorkspaceCampaignId = data.items[0].id;
        if (currentWorkspaceCampaignId && data.items.some(c => c.id === currentWorkspaceCampaignId)) {
          select.value = currentWorkspaceCampaignId;
        }
      }
      const ganttSelect = document.getElementById('ganttCampaignSelect');
      if (ganttSelect) {
        ganttSelect.innerHTML = data.items.map(c => `<option value="${c.id}">${c.id} · ${c.title}</option>`).join('') || `<option value="">No campaigns</option>`;
        if (!currentGanttCampaignId && data.items.length) currentGanttCampaignId = data.items[0].id;
        if (currentGanttCampaignId && data.items.some(c => c.id === currentGanttCampaignId)) {
          ganttSelect.value = currentGanttCampaignId;
        }
      }
      if (deepTarget) requestAnimationFrame(() => revealListTarget(deepTarget));
      return data.items;
    }

    function parseGanttDate(value) {
      if (!value) return null;
      const d = parseDateLikeLocal(value);
      if (Number.isNaN(d.getTime())) return null;
      return d;
    }

    function toIsoLocalDate(d) {
      if (!(d instanceof Date) || Number.isNaN(d.getTime())) return null;
      const yyyy = String(d.getFullYear()).padStart(4, '0');
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      return `${yyyy}-${mm}-${dd}`;
    }

    function buildGanttRows(ws) {
      const rows = [];
      const campaignStart = parseGanttDate(ws?.campaign?.timeframe_start);
      const campaignEnd = parseGanttDate(ws?.campaign?.timeframe_due);
      if (campaignStart || campaignEnd) {
        const campaignHealth = String(
          ws?.campaign?.health
          || ws?.campaign?.campaign_health
          || ws?.health_summary?.overall_status
          || 'not_started'
        ).toLowerCase();
        rows.push({
          kind: 'campaign',
          name: ws?.campaign?.title || 'Campaign',
          start: campaignStart || campaignEnd,
          end: campaignEnd || campaignStart,
          campaign: {
            ...(ws?.campaign || {}),
            health: campaignHealth,
            deliverables: [],
            work_steps: [],
          },
        });
      }

      const milestones = Array.isArray(ws?.timeline?.milestones) ? ws.timeline.milestones : [];
      for (const m of milestones) {
        const target = parseGanttDate(m?.current_target_date) || parseGanttDate(m?.baseline_date);
        if (!target) continue;
        rows.push({
          kind: 'milestone',
          name: m?.name || 'Milestone',
          start: target,
          end: target,
          milestone: {
            ...(m || {}),
          },
          campaign: {
            id: ws?.campaign?.id || '-',
            title: ws?.campaign?.title || '-',
          },
        });
      }

      const steps = Array.isArray(ws?.workflow_steps?.items) ? ws.workflow_steps.items : [];
      const persistedStages = Array.isArray(ws?.stages) ? ws.stages : [];
      const stageGroups = {};
      for (const s of steps) {
        const key = String(
          s?.stage_name
          || (persistedStages.find(st => String(st?.id || '') === String(s?.stage_id || ''))?.name)
          || s?.stage
          || s?.deliverable_stage
          || 'planning'
        ).toLowerCase();
        if (!stageGroups[key]) stageGroups[key] = [];
        stageGroups[key].push(s);
      }
      const stageOrder = ['planning', 'production', 'promotion', 'reporting'];
      const stageLabel = {
        planning: 'Planning',
        production: 'Production',
        promotion: 'Promotion',
        reporting: 'Reporting',
      };
      const persistedStageKeys = persistedStages.map(st => String(st?.name || '').toLowerCase()).filter(Boolean);
      const orderedStageKeys = [
        ...stageOrder,
        ...persistedStageKeys.filter(k => !stageOrder.includes(k)),
        ...Object.keys(stageGroups).filter(k => !stageOrder.includes(k) && !persistedStageKeys.includes(k)),
      ];
      const processedStepIds = new Set();
      const stageSort = (a, b) => {
        const aStart = parseGanttDate(a.current_start) || parseGanttDate(a.current_due);
        const bStart = parseGanttDate(b.current_start) || parseGanttDate(b.current_due);
        if (aStart && bStart) return aStart - bStart;
        if (aStart && !bStart) return -1;
        if (!aStart && bStart) return 1;
        return String(a.name || a.id || '').localeCompare(String(b.name || b.id || ''));
      };
      const pushStepRow = (s) => {
        const start = parseGanttDate(s.current_start) || parseGanttDate(s.current_due);
        const end = parseGanttDate(s.current_due) || start;
        if (!start && !end) return;
        rows.push({
          kind: 'step',
          name: s.name || s.id || 'Step',
          start: start || end,
          end: end || start,
          level: 1,
          step: s,
          deliverable: {
            title: s.linked_deliverable_title || s.deliverable_title || '-',
            id: s.linked_deliverable_id || null,
          },
          campaign: {
            id: ws?.campaign?.id || s.campaign_id || '-',
            title: ws?.campaign?.title || '-',
          },
          parent_stage_key: String(
            s?.stage_name
            || (persistedStages.find(st => String(st?.id || '') === String(s?.stage_id || ''))?.name)
            || s?.stage
            || s?.deliverable_stage
            || 'planning'
          ).toLowerCase(),
        });
        if (s.id) processedStepIds.add(String(s.id));
      };
      for (const key of orderedStageKeys) {
        const stageSteps = stageGroups[key] || [];
        const persisted = persistedStages.find(st => String(st?.name || '').toLowerCase() === key) || null;
        const starts = stageSteps
          .map(s => parseGanttDate(stepWindowStart(s)))
          .filter(Boolean)
          .sort((a, b) => a - b);
        const ends = stageSteps
          .map(s => parseGanttDate(stepWindowEnd(s)))
          .filter(Boolean)
          .sort((a, b) => a - b);
        const start = starts[0] || parseGanttDate(persisted?.current_start || persisted?.baseline_start) || campaignStart || campaignEnd;
        const end = ends[ends.length - 1] || parseGanttDate(persisted?.current_due || persisted?.baseline_due) || start;
        if (!start && !end) continue;
        rows.push({
          kind: 'stage',
          name: stageLabel[key] || key,
          start: start || end,
          end: end || start,
          stage: {
            id: persisted?.display_id || `${ws?.campaign?.id || 'campaign'}_${key}`,
            name: stageLabel[key] || key,
            status: persisted?.status || deriveStageStatus(stageSteps),
            health: persisted?.health || deriveStageHealth(stageSteps),
            timeframe: deriveStageTimeframe(stageSteps),
            due: deriveStageDue(stageSteps),
            campaign_id: ws?.campaign?.id || '-',
            campaign_name: ws?.campaign?.title || '-',
            steps: stageSteps,
          },
          stage_key: key,
        });
        for (const s of [...stageSteps].sort(stageSort)) {
          pushStepRow(s);
        }
      }

      for (const s of steps) {
        if (s.id && processedStepIds.has(String(s.id))) continue;
        pushStepRow(s);
      }

      return rows;
    }

    function ganttBounds(rows) {
      const starts = rows.map(r => r.start).filter(Boolean);
      const ends = rows.map(r => r.end).filter(Boolean);
      if (!starts.length && !ends.length) return null;
      const minStart = starts.length ? new Date(Math.min(...starts.map(d => d.getTime()))) : new Date(Math.min(...ends.map(d => d.getTime())));
      const maxEnd = ends.length ? new Date(Math.max(...ends.map(d => d.getTime()))) : new Date(Math.max(...starts.map(d => d.getTime())));
      // Show one full month either side of campaign content for easier scroll context.
      const startMonth = startOfMonth(minStart);
      const endMonth = startOfMonth(maxEnd);
      const paddedStart = addMonths(startMonth, -1);
      const paddedEndMonth = addMonths(endMonth, 1);
      const paddedEnd = new Date(paddedEndMonth.getFullYear(), paddedEndMonth.getMonth() + 1, 0);
      paddedStart.setHours(0, 0, 0, 0);
      paddedEnd.setHours(0, 0, 0, 0);
      return { start: paddedStart, end: paddedEnd };
    }

    function ganttBarStyle(row, bounds) {
      const totalMs = Math.max(bounds.end.getTime() - bounds.start.getTime(), 86400000);
      const startMs = (row.start || bounds.start).getTime();
      const endMs = (row.end || row.start || bounds.start).getTime();
      const leftPct = ((startMs - bounds.start.getTime()) / totalMs) * 100;
      const widthPct = (Math.max(endMs - startMs, 86400000) / totalMs) * 100;
      return `left:${Math.max(0, leftPct)}%;width:${Math.max(1, widthPct)}%;`;
    }

    function ganttTodayLeftPercent(bounds) {
      if (!bounds?.start || !bounds?.end) return null;
      const totalMs = Math.max(bounds.end.getTime() - bounds.start.getTime(), 86400000);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const pct = ((today.getTime() - bounds.start.getTime()) / totalMs) * 100;
      if (pct < 0 || pct > 100) return null;
      return Math.max(0, Math.min(100, pct));
    }

    function ganttToneForKind(kind) {
      const k = String(kind || '').toLowerCase();
      if (k === 'scope') return 'tone-violet';
      if (k === 'campaign') return 'tone-cobalt';
      if (k === 'stage') return 'tone-sage';
      if (k === 'milestone') return 'tone-cobalt';
      if (k === 'deliverable') return 'tone-amber';
      if (k === 'step') return 'tone-rust';
      return 'tone-cobalt';
    }

    function ganttStatusDotClass(value) {
      const v = normalizeStatusValue(value);
      if (v === 'in_progress') return 'status-in-progress';
      if (v === 'on_hold') return 'status-on-hold';
      if (v === 'blocked_dependency') return 'status-blocked-dependency';
      if (v === 'blocked_client' || v === 'blocked_internal') return 'status-blocked';
      if (v === 'done') return 'status-done';
      if (v === 'cancelled') return 'status-cancelled';
      return 'status-not-started';
    }

    function ganttBarContent(row) {
      const kind = String(row?.kind || '').toLowerCase();
      if (kind === 'campaign') {
        const health = String(row?.campaign?.health || 'not_started').toLowerCase();
        let cls = '';
        let label = 'Not due';
        if (health === 'on_track') { cls = 'ok'; label = 'On Track'; }
        else if (health === 'at_risk') { cls = 'warn'; label = 'At Risk'; }
        else if (health === 'off_track') { cls = 'risk'; label = 'Off Track'; }
        return `<span>${row?.name || ''}</span><span class='gantt-health-pill ${cls}'>${label}</span>`;
      }
      if (kind === 'milestone') {
        return `<span>${row?.name || ''}</span>`;
      }
      if (kind !== 'step') {
        return `${row?.name || ''}`;
      }
      const title = String(row?.name || 'Step');
      return `<span>${title}</span>`;
    }

    function ganttStepSuffix(row) {
      if (String(row?.kind || '').toLowerCase() !== 'step') return '';
      const statusClass = ganttStatusDotClass(row?.step?.status);
      const owner = String(row?.step?.owner_initials || '--').trim() || '--';
      const ownerName = String(row?.step?.owner_name || row?.step?.owner_user_name || '').trim() || null;
      return `<span class='gantt-step-suffix'><span class='gantt-status-dot ${statusClass}' aria-hidden='true'></span><span class='gantt-owner-pill'>${userPill(owner, false, ownerName, { userId: row?.step?.next_owner_user_id || '' })}</span></span>`;
    }

    function updateGanttBarOverflowLabels() {
      const wraps = Array.from(document.querySelectorAll('#ganttBody .gantt-bar-wrap'));
      for (const wrap of wraps) {
        wrap.classList.remove('overflow');
        const btn = wrap.querySelector('.gantt-bar');
        if (!(btn instanceof HTMLElement)) continue;
        if (btn.scrollWidth > (btn.clientWidth + 2)) {
          wrap.classList.add('overflow');
        }
      }
    }

    function startOfMonth(d) {
      return new Date(d.getFullYear(), d.getMonth(), 1);
    }

    function addMonths(d, count) {
      return new Date(d.getFullYear(), d.getMonth() + count, 1);
    }

    function addDaysLocal(d, days) {
      const next = new Date(d.getTime());
      next.setDate(next.getDate() + days);
      return next;
    }

    function buildGanttTicks(bounds, viewMode) {
      const ticks = [];
      if (viewMode === 'week') {
        let cur = mondayOf(bounds.start);
        const end = mondayOf(bounds.end);
        while (cur <= end) {
          ticks.push({
            key: toIsoLocalDate(cur),
            label: `W/C ${cur.toLocaleDateString(undefined, { day: '2-digit', month: 'short' })}`,
          });
          cur = addDaysLocal(cur, 7);
        }
        return ticks;
      }
      let cur = startOfMonth(bounds.start);
      const end = startOfMonth(bounds.end);
      while (cur <= end) {
        ticks.push({
          key: toIsoLocalDate(cur),
          label: cur.toLocaleDateString(undefined, { month: 'short', year: '2-digit' }),
        });
        cur = addMonths(cur, 1);
      }
      return ticks;
    }

    function selectedGanttKinds() {
      const container = document.getElementById('ganttKinds');
      if (!container) return new Set(['campaign', 'milestone', 'stage', 'step']);
      const selected = [...container.querySelectorAll("input[type='checkbox']")]
        .filter(o => o.checked)
        .map(o => String(o.value || '').toLowerCase())
        .filter(v => v === 'campaign' || v === 'milestone' || v === 'stage' || v === 'step');
      if (!selected.length) return new Set(['campaign', 'milestone', 'stage', 'step']);
      return new Set(selected);
    }

    function syncGanttKindsControl() {
      const container = document.getElementById('ganttKinds');
      if (!container) return;
      for (const input of [...container.querySelectorAll("input[type='checkbox']")]) {
        const val = String(input.value || '').toLowerCase();
        input.checked = currentGanttKinds.has(val);
      }
    }

    function setGanttView(viewMode) {
      currentGanttView = viewMode === 'week' ? 'week' : 'month';
      const monthBtn = document.getElementById('ganttMonthBtn');
      const weekBtn = document.getElementById('ganttWeekBtn');
      if (monthBtn) monthBtn.classList.toggle('primary', currentGanttView === 'month');
      if (weekBtn) weekBtn.classList.toggle('primary', currentGanttView === 'week');
      renderGantt().catch(err => log('Gantt render failed', String(err)));
    }

    async function onGanttKindsChange() {
      currentGanttKinds = selectedGanttKinds();
      await renderGantt();
    }

    async function onGanttCampaignChange() {
      const select = document.getElementById('ganttCampaignSelect');
      currentGanttCampaignId = select?.value || null;
      ganttCollapsedStageKeys = new Set();
      ganttCollapseInitCampaignId = null;
      if (currentGanttCampaignId) ganttInitialSnapDone.delete(currentGanttCampaignId);
      await renderGantt();
    }

    function toggleGanttStage(stageKeyToken) {
      let stageKey = '';
      try {
        stageKey = decodeURIComponent(String(stageKeyToken || ''));
      } catch (_) {
        stageKey = String(stageKeyToken || '');
      }
      if (!stageKey) return;
      if (ganttCollapsedStageKeys.has(stageKey)) {
        ganttCollapsedStageKeys.delete(stageKey);
      } else {
        ganttCollapsedStageKeys.add(stageKey);
      }
      renderGantt().catch(err => log('Gantt render failed', String(err)));
    }

    function snapGanttToFirstObject() {
      const body = document.getElementById('ganttBody');
      if (!(body instanceof HTMLElement)) return;
      const firstBar = body.querySelector('.gantt-track:not(.hidden) .gantt-bar-wrap');
      const firstTrack = body.querySelector('.gantt-track:not(.hidden)');
      if (!(firstBar instanceof HTMLElement) || !(firstTrack instanceof HTMLElement)) return;
      const bodyRect = body.getBoundingClientRect();
      const trackRect = firstTrack.getBoundingClientRect();
      const barRect = firstBar.getBoundingClientRect();
      const timelineLeftInsideBody = trackRect.left - bodyRect.left;
      const barLeftInsideBody = barRect.left - bodyRect.left;
      const desired = Math.max(0, body.scrollLeft + (barLeftInsideBody - timelineLeftInsideBody) - 12);
      body.scrollLeft = desired;
    }

    async function renderGantt() {
      const body = document.getElementById('ganttBody');
      const meta = document.getElementById('ganttMeta');
      const select = document.getElementById('ganttCampaignSelect');
      if (!body || !meta || !select) return;

      if (!select.options.length) {
        const campaigns = await renderCampaigns();
        if (!currentGanttCampaignId && campaigns.length) currentGanttCampaignId = campaigns[0].id;
        if (currentGanttCampaignId) select.value = currentGanttCampaignId;
      }
      if (!currentGanttCampaignId) {
        body.innerHTML = "<div class='sub' style='padding:12px;'>No campaign selected.</div>";
        meta.textContent = 'No campaigns available.';
        return;
      }

      const ws = await api(`/api/campaigns/${encodeURIComponent(currentGanttCampaignId)}/workspace`);
      syncGanttKindsControl();
      const allRows = buildGanttRows(ws);
      const stageKeys = allRows
        .filter(r => String(r.kind || '').toLowerCase() === 'stage')
        .map(r => String(r.stage_key || '').toLowerCase())
        .filter(Boolean);
      if (ganttCollapseInitCampaignId !== currentGanttCampaignId) {
        ganttCollapsedStageKeys = new Set(stageKeys);
        ganttCollapseInitCampaignId = currentGanttCampaignId;
      }
      const selectedKinds = selectedGanttKinds();
      currentGanttKinds = selectedKinds;
      const rows = allRows.filter(r => selectedKinds.has(String(r.kind || '').toLowerCase()));
      const bounds = ganttBounds(rows);
      meta.textContent = `${ws.campaign.title} · ${niceDate(ws.campaign.timeframe_start)} → ${niceDate(ws.campaign.timeframe_due)}`;
      if (!bounds || !rows.length) {
        body.innerHTML = "<div class='sub' style='padding:12px;'>No items for the selected object types.</div>";
        return;
      }

      const ticks = buildGanttTicks(bounds, currentGanttView);
      const tickLabels = ticks.map(t => `<div class='gantt-head-time-cell'>${t.label}</div>`);
      const cols = Math.max(1, ticks.length);
      const todayLeftPct = ganttTodayLeftPercent(bounds);
      const unitWidth = currentGanttView === 'week' ? 220 : 260;
      const monthBtn = document.getElementById('ganttMonthBtn');
      const weekBtn = document.getElementById('ganttWeekBtn');
      if (monthBtn) monthBtn.classList.toggle('primary', currentGanttView === 'month');
      if (weekBtn) weekBtn.classList.toggle('primary', currentGanttView === 'week');

      const rowHtml = rows.map(r => `
        <div class='gantt-row-label ${r.kind === 'stage' ? 'stage-row' : ''} ${Number(r.level || 0) > 0 ? `level-${Number(r.level || 0)}` : ''} ${((selectedKinds.has('stage')) && r.parent_stage_key && ganttCollapsedStageKeys.has(r.parent_stage_key)) ? 'hidden' : ''}' ${r.kind === 'stage' ? `onclick='toggleGanttStage("${encodeURIComponent(String(r.stage_key || ''))}")'` : ''}>
          ${r.kind === 'stage' ? `<span class='gantt-stage-chevron'>${ganttCollapsedStageKeys.has(r.stage_key) ? '▸' : '▾'}</span>` : ''}
          <span class='tag ${objectTypeTagClass(r.kind)}'>${r.kind}</span>
          <span>${r.name}</span>
        </div>
        <div class='gantt-track ${((selectedKinds.has('stage')) && r.parent_stage_key && ganttCollapsedStageKeys.has(r.parent_stage_key)) ? 'hidden' : ''}' style='--gantt-cols:${cols};'>
          ${todayLeftPct == null ? '' : `<div class='gantt-today-line' style='left:${todayLeftPct}%;' aria-hidden='true'></div>`}
          <div class='gantt-bar-wrap' style='${ganttBarStyle(r, bounds)}'>
            <button class='gantt-bar cap-pill ${ganttToneForKind(r.kind)}' onclick='openItemPopoverByPayload(this, "${encodePopoverPayload((() => {
              const p = {
                title: r.name || 'Item',
                module_type: r.kind,
                campaign: r.campaign || null,
                deliverable: r.deliverable || null,
                step: r.step || null,
                stage: r.stage || null,
                details: [
                  `Start: ${toIsoLocalDate(r.start) || '-'}`,
                  `End: ${toIsoLocalDate(r.end) || '-'}`,
                ],
                open_path: r.campaign?.id ? '/campaigns' : '/gantt',
                open_label: r.campaign?.id ? 'Open Campaigns' : 'Open Gantt',
              };
              p.target_type = String(r.kind || '').toLowerCase();
              p.target_id =
                (p.target_type === 'campaign' ? (r.campaign?.id || ws?.campaign?.id || '') :
                p.target_type === 'milestone' ? (r.milestone?.id || '') :
                p.target_type === 'deliverable' ? (r.deliverable?.id || '') :
                p.target_type === 'step' ? (r.step?.id || '') :
                p.target_type === 'stage' ? (r.stage?.id || '') : '');
              p.campaign_id = r.campaign?.id || r.stage?.campaign_id || r.step?.campaign_id || r.deliverable?.campaign_id || ws?.campaign?.id || '';
              if (p.target_type === 'milestone') {
                p.details = [
                  `Milestone ID: ${r.milestone?.id || '-'}`,
                  `Baseline: ${r.milestone?.baseline_date ? niceDate(r.milestone.baseline_date) : '-'}`,
                  `Current target: ${r.milestone?.current_target_date ? niceDate(r.milestone.current_target_date) : '-'}`,
                  `Achieved: ${r.milestone?.achieved_at ? niceDate(r.milestone.achieved_at) : '-'}`,
                ];
                p.open_path = '/campaigns';
                p.open_label = 'Open Campaign';
              }
              p.open_deep_link = popoverOpenDeepLinkForPayload(p);
              return p;
            })())}")' title='${r.name}: ${niceDate(toIsoLocalDate(r.start))} → ${niceDate(toIsoLocalDate(r.end))}'>
              ${ganttBarContent(r)}
            </button>
            <span class='gantt-bar-side'>${r.name}</span>
            ${ganttStepSuffix(r)}
          </div>
        </div>
      `).join('');

      body.innerHTML = `
        <div class='gantt-grid' style='--gantt-cols:${cols};--gantt-unit-width:${unitWidth}px;'>
          <div class='gantt-head sticky-col'>Object</div>
          <div class='gantt-head time-head'>${tickLabels.join('')}</div>
          ${rowHtml}
        </div>
      `;
      requestAnimationFrame(updateGanttBarOverflowLabels);
      if (currentGanttCampaignId && !ganttInitialSnapDone.has(currentGanttCampaignId)) {
        requestAnimationFrame(() => {
          snapGanttToFirstObject();
          ganttInitialSnapDone.add(currentGanttCampaignId);
        });
      }
    }

    function setWorkspaceTab(tab) {
      currentWorkspaceTab = tab;
      renderCampaignWorkspace().catch(err => log('Workspace render failed', String(err)));
    }

    async function onWorkspaceCampaignChange() {
      const select = document.getElementById('workspaceCampaignSelect');
      currentWorkspaceCampaignId = select.value || null;
      workspaceCache = null;
      await renderCampaignWorkspace();
    }

    async function openCampaignWorkspace(campaignId) {
      window.location.href = `/campaigns/${encodeURIComponent(campaignId)}`;
    }

    async function deleteCampaign(campaignId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        if (!canUseControl('delete_campaign', currentRole)) throw new Error('You do not have permission to delete campaigns');
        if (!confirm(`Delete campaign ${campaignId}? This also removes associated deliverables, steps, risks, and related operational records.`)) return;
        await api(`/api/campaigns/${encodeURIComponent(campaignId)}?actor_user_id=${encodeURIComponent(currentActorId)}`, {
          method: 'DELETE',
        });
        if (currentWorkspaceCampaignId === campaignId) {
          currentWorkspaceCampaignId = null;
          workspaceCache = null;
        }
        toast(`Campaign ${campaignId} deleted`, 'success');
        await Promise.all([renderCampaigns(), renderMyWork(currentRole, currentActorId), renderCapacity()]);
      } catch (err) {
        toast(`Unable to delete campaign: ${String(err)}`, 'error');
        log('Campaign delete failed', String(err));
      }
    }

    async function deleteDeliverable(deliverableId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        if (!canUseControl('delete_deliverable', currentRole)) throw new Error('You do not have permission to delete deliverables');
        if (!confirm(`Delete deliverable ${deliverableId}? This cannot be undone.`)) return;
        await api(`/api/deliverables/${encodeURIComponent(deliverableId)}?actor_user_id=${encodeURIComponent(currentActorId)}`, {
          method: 'DELETE',
        });
        if (selectedDeliverableId === deliverableId) selectedDeliverableId = null;
        workspaceCache = null;
        toast(`Deliverable ${deliverableId} deleted`, 'success');
        await Promise.all([renderCampaignWorkspace(), renderCampaigns(), renderMyWork(currentRole, currentActorId), renderCapacity()]);
      } catch (err) {
        toast(`Unable to delete deliverable: ${String(err)}`, 'error');
        log('Deliverable delete failed', String(err));
      }
    }

    function workspaceTable(headers, rows) {
      return `
        <table>
          <thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
          <tbody>${rows || `<tr><td colspan="${headers.length}" class='sub'>No data.</td></tr>`}</tbody>
        </table>
      `;
    }

    async function renderCampaignWorkspace() {
      const body = document.getElementById('workspaceBody');
      const meta = document.getElementById('workspaceMeta');
      if (!body || !meta) return;
      if (!currentWorkspaceCampaignId) {
        body.innerHTML = "<div class='sub'>No campaign selected.</div>";
        meta.textContent = 'Select a campaign to open workspace.';
        return;
      }
      if (!workspaceCache || workspaceCache.campaign.id !== currentWorkspaceCampaignId) {
        workspaceCache = await api(`/api/campaigns/${currentWorkspaceCampaignId}/workspace`);
      }
      const ws = workspaceCache;
      meta.textContent = `${ws.campaign.id} · ${ws.campaign.title} · ${statusLabel(ws.campaign.status)}`;

      if (currentWorkspaceTab === 'overview') {
        const canManageAssignments = canUseControl('manage_campaign_assignments', currentRole);
        const canManageSteps = canUseControl('manage_step', currentRole);
        const canEditDue = canUseControl('override_step_due', currentRole);
        const canEditStage = canUseControl('edit_deliverable_stage', currentRole);
        const canAdvanceDeliverable = canUseControl('advance_deliverable', currentRole);
        const worstReason = ws.health_summary?.worst_signal?.reason || 'No active signal';
        const nextAction = ws.next_action
          ? `${ws.next_action.action} · ${userName(ws.next_action.owner_user_id)} · Due ${ws.next_action.due || '-'}`
          : 'No action required';
        const assignments = ws.campaign.assignments || {};
        const assignmentEditorHtml = canManageAssignments
          ? `
            <div style='margin-top:8px;'>
              <div class='sub'><strong>Campaign Assignments</strong></div>
              <div class='actions' style='margin-top:8px; flex-wrap:wrap; align-items:flex-end;'>
                <div><label class='sub'>AM</label><select id='wsAssign_am'>${assignmentSelectOptionsForRole('am', assignments.am || '')}</select></div>
                <div><label class='sub'>CM</label><select id='wsAssign_cm'>${assignmentSelectOptionsForRole('cm', assignments.cm || '')}</select></div>
                <div><label class='sub'>CC</label><select id='wsAssign_cc'>${assignmentSelectOptionsForRole('cc', assignments.cc || '')}</select></div>
                <div><label class='sub'>CCS</label><select id='wsAssign_ccs'>${assignmentSelectOptionsForRole('ccs', assignments.ccs || '')}</select></div>
                <div><label class='sub'>DN</label><select id='wsAssign_dn'>${assignmentSelectOptionsForRole('dn', assignments.dn || '')}</select></div>
                <div><label class='sub'>MM</label><select id='wsAssign_mm'>${assignmentSelectOptionsForRole('mm', assignments.mm || '')}</select></div>
                <div><button onclick='saveCampaignAssignments()'>Save Assignments</button></div>
              </div>
            </div>
          `
          : `
            <div class='queue-meta' style='margin-top:8px;'>
              <span>AM: ${userName(assignments.am || '')}</span>
              <span>CM: ${userName(assignments.cm || '')}</span>
              <span>CC: ${userName(assignments.cc || '')}</span>
              <span>CCS: ${userName(assignments.ccs || '')}</span>
              <span>DN: ${userName(assignments.dn || '')}</span>
              <span>MM: ${userName(assignments.mm || '')}</span>
            </div>
          `;
        const deliverablesByCampaignLabel = {};
        const campaignLabel = ws.campaign?.sprint_label || 'Campaign';
        for (const d of (ws.deliverables.items || [])) {
          if (!deliverablesByCampaignLabel[campaignLabel]) deliverablesByCampaignLabel[campaignLabel] = [];
          deliverablesByCampaignLabel[campaignLabel].push(d);
        }
        const workspaceGroups = (ws.sprints || []).length ? (ws.sprints || []) : [{ id: campaignLabel, sections: ws.sections || {} }];
        const groupedDeliverablesHtml = workspaceGroups.map(sprint => {
          const sprintKey = sprint.id;
          const sprintItems = deliverablesByCampaignLabel[campaignLabel] || [];
          const sectionMap = sprint.sections || {};
          const rollup = { not_started: 0, in_progress: 0, done: 0 };
          for (const d of sprintItems) {
            const status = normalizeStatusValue(d.status || '');
            if (status === 'not_started') rollup.not_started += 1;
            else if (status === 'done') rollup.done += 1;
            else rollup.in_progress += 1;
          }
          const deliverableCards = sprintItems.map(d => {
            const deliverableEditMode = isModuleEditing('deliverable', d.id || '');
            const dueControl = (canEditDue && deliverableEditMode)
              ? `
                <div class='actions' style='margin-top:0; align-items:center; gap:6px;'>
                  <input id='delDue_${d.id}' type='date' value='${(d.current_due || '').slice(0, 10)}' />
                  <button onclick="saveDeliverableDue('${d.id}')">Save</button>
                </div>
              `
              : '';
            const stageControl = (canEditStage && deliverableEditMode)
              ? `
                <div class='actions' style='margin-top:0; gap:6px;'>
                  <select id='delStage_${d.id}'>
                    <option value='planning' ${(d.stage || 'planning') === 'planning' ? 'selected' : ''}>Planning</option>
                    <option value='production' ${(d.stage || 'planning') === 'production' ? 'selected' : ''}>Production</option>
                    <option value='promotion' ${(d.stage || 'planning') === 'promotion' ? 'selected' : ''}>Promotion</option>
                    <option value='reporting' ${(d.stage || 'planning') === 'reporting' ? 'selected' : ''}>Reporting</option>
                  </select>
                  <button onclick="saveDeliverableStage('${d.id}')">Save</button>
                </div>
              `
              : '';
            return `
              <div>
                ${deliverableModuleCard(
                  {
                    ...d,
                    campaign_name: ws.campaign?.title || d.campaign_name || '-',
                  },
                  {
                    idPrefix: `workspace_${ws.campaign?.id || 'campaign'}`,
                    statusControlHtml: canAdvanceDeliverable ? deliverableStatusDropdown(d, 'workspace') : '',
                    stageControlHtml: stageControl,
                    dueControlHtml: dueControl,
                    actionsHtml: `
                      <button onclick="selectDeliverableForHistory('${d.id}')">Reviews</button>
                      ${canUseControl('delete_deliverable', currentRole) ? `<button class='danger' onclick="deleteDeliverable('${d.id}')">Delete</button>` : ''}
                    `,
                  }
                )}
              </div>
            `;
          }).join('');

          const sectionOrder = ['planning', 'production', 'promotion', 'reporting'];
          const stageAccordions = sectionOrder
            .filter(key => Array.isArray(sectionMap[key]) && sectionMap[key].length > 0)
            .map(key => {
              const cards = (sectionMap[key] || []).map(st => `
                ${stepModuleCard({
                  step: st,
                  deliverable: { title: st.deliverable_title || `${campaignLabel} · Planning` },
                  campaign: { id: ws.campaign.id, title: ws.campaign.title },
                  derived: { is_overdue: !!(st.current_due && st.current_due < isoDate(new Date())) },
                }, canManageSteps ? {
                  showControls: true,
                  idPrefix: `workspace_${ws.campaign?.id || 'campaign'}`,
                  ownerId: `wsStepOwner_${st.id}`,
                  statusId: `wsStepAction_${st.id}`,
                  dropdownContext: 'workspace',
                  reasonId: `wsStepReason_${st.id}`,
                  onSave: `manageWorkspaceStep('${st.id}')`,
                } : {})}
                ${(canEditDue && isModuleEditing('step', st.id || '')) ? `<div class='module-row'><span>Due:</span><input id='wsStepDue_${st.id}' type='date' value='${(st.current_due || '').slice(0, 10)}' /></div>` : ''}
              `).join('');
              const sectionLabel = key.charAt(0).toUpperCase() + key.slice(1);
              return stageModuleCard(
                {
                  name: sectionLabel,
                  status: deriveStageStatus(sectionMap[key] || []),
                  health: deriveStageHealth(sectionMap[key] || []),
                  timeframe: deriveStageTimeframe(sectionMap[key] || []),
                  campaign_name: ws.campaign?.title || '-',
                  steps: sectionMap[key] || [],
                },
                {
                  stepsHtml: `<div class='queue-list'>${cards || "<div class='sub'>No steps.</div>"}</div>`,
                }
              );
            })
            .join('');

          const deliverablesAccordion = `
            <details class='ops-accordion'>
              <summary>
                Deliverables · ${sprintItems.length}
              </summary>
              <div style='padding:0 10px 10px 10px;'>
                <div class='queue-list'>${deliverableCards || "<div class='sub'>No deliverables.</div>"}</div>
              </div>
            </details>
          `;

          const workAccordion = `
            <details class='ops-accordion'>
              <summary>
                Work · ${(Object.values(sectionMap || {}).reduce((n, arr) => n + (Array.isArray(arr) ? arr.length : 0), 0))} step(s)
              </summary>
              <div style='padding:0 10px 10px 10px;'>
                ${stageAccordions || "<div class='sub'>No work items.</div>"}
              </div>
            </details>
          `;

          return `
            <details class='ops-accordion surface-2'>
              <summary>
                ${sprintKey} · ${sprintItems.length} deliverable${sprintItems.length === 1 ? '' : 's'} · Not started ${rollup.not_started} · In progress ${rollup.in_progress} · Done ${rollup.done}
              </summary>
              <div style='padding:0 10px 10px 10px;'>
                ${deliverablesAccordion}
                ${workAccordion}
              </div>
            </details>
          `;
        }).join('');
        body.innerHTML = `
          ${campaignModuleCard(ws.campaign)}
          <div class='queue-meta'>
            <span>Sprints: ${ws.overview.sprints_total}</span>
            <span>Deliverables: ${ws.overview.deliverables_total}</span>
            <span>Open steps: ${ws.overview.workflow_steps_open}</span>
            <span>Open system risks: ${ws.overview.open_system_risks}</span>
            <span>Open manual risks: ${ws.overview.open_manual_risks}</span>
          </div>
          <div class='queue-meta' style='margin-top:8px;'>
            <span>Health: ${healthChip(ws.health_summary?.overall_status || 'not_started')}</span>
            <span>Worst signal: ${worstReason}</span>
            <span>Next action: ${nextAction}</span>
          </div>
          ${assignmentEditorHtml}
          <div class='spacer-md'></div>
          <div><strong>Deliverables</strong></div>
          ${groupedDeliverablesHtml || "<div class='sub'>No deliverables.</div>"}
        `;
        return;
      }
      if (currentWorkspaceTab === 'sprints') {
        body.innerHTML = workspaceTable(
          ['Sprint', 'Baseline Start', 'Current Start', 'Deliverables', 'Complete'],
          ws.sprints.map(s => `<tr><td>${s.id}</td><td>${s.baseline_start || '-'}</td><td>${s.current_start || '-'}</td><td>${s.deliverables_total}</td><td>${s.deliverables_complete}</td></tr>`).join('')
        );
        return;
      }
      if (currentWorkspaceTab === 'tasks') {
        const campaignSteps = (ws.workflow_steps?.items || [])
          .sort((a, b) => {
            const da = a.current_due || '9999-12-31';
            const db = b.current_due || '9999-12-31';
            if (da !== db) return da.localeCompare(db);
            return String(a.name || '').localeCompare(String(b.name || ''));
          });
        const canEditDue = canUseControl('override_step_due', currentRole);
        const canManageSteps = canUseControl('manage_step', currentRole);
        const stepsByParent = {};
        for (const step of campaignSteps) {
          const stageKey = String(step.stage_name || 'planning').toLowerCase();
          const key = `STAGE:${stageKey}`;
          if (!stepsByParent[key]) stepsByParent[key] = [];
          stepsByParent[key].push(step);
        }
        const orderedKeys = Object.keys(stepsByParent).sort();

        const accordionHtml = orderedKeys.map(parentKey => {
          const steps = stepsByParent[parentKey] || [];
          if (!steps.length) return '';
          const first = steps[0] || {};
          const parentTitle = `${formatStageLabel(first.stage_name || 'planning', 'Planning')} · Steps`;
          const counts = { planned: 0, active: 0, done: 0 };
          for (const s of steps) {
            const state = normalizeStatusValue(s.status || s.step_state || '');
            if (state === 'done') counts.done += 1;
            else if (state === 'not_started') counts.planned += 1;
            else counts.active += 1;
          }
          const cards = steps.map(s => {
            const stepEditMode = isModuleEditing('step', s.id || '');
            const dueCell = (canEditDue && stepEditMode) ? `<input id='taskDue_${s.id}' type='date' value='${(s.current_due || '').slice(0, 10)}' />` : `${s.current_due || '-'}`;
            return `
              ${stepModuleCard({
                step: s,
                deliverable: { title: s.linked_deliverable_title || s.deliverable_title || '-' },
                campaign: { id: s.campaign_id || ws.campaign.id, title: ws.campaign.title },
                derived: { is_overdue: !!(s.current_due && s.current_due < isoDate(new Date())) },
              }, canManageSteps ? {
                showControls: true,
                ownerId: `taskOwner_${s.id}`,
                statusId: `taskAction_${s.id}`,
                dropdownContext: 'task',
                reasonId: `taskReason_${s.id}`,
                onSave: `saveWorkspaceTaskDue('${s.id}')`,
              } : {})}
              <div class='module-row'><span>Due:</span>${dueCell}</div>
              <div class='actions' style='margin-top:0; flex-wrap:wrap;'>
                <button onclick='openItemPopoverByPayload(this, "${encodePopoverPayload({
                  title: s.name || s.id || "Task",
                  module_type: "step",
                  step: s,
                  deliverable: { id: s.linked_deliverable_id || null, title: s.linked_deliverable_title || s.deliverable_title || '-' },
                  campaign: { id: s.campaign_id || ws.campaign.id, title: ws.campaign.title },
                  details: [
                    `Task ID: ${s.id || "-"}`,
                    `Campaign: ${s.campaign_id || "-"}`,
                    `Parent: ${s.parent_type || "-"}`,
                    `Stage: ${formatStageLabel(s.stage_name || s.stage || "-", "-")}`,
                    `Linked deliverable: ${s.linked_deliverable_title || s.deliverable_title || "-"}`,
                    `Owner role: ${s.owner_role || "-"}`,
                    `Assigned user: ${userName(s.next_owner_user_id || "")}`,
                    `State: ${s.step_state || "-"}`,
                    `Due: ${s.current_due || "-"}`,
                    `Waiting: ${s.waiting_on_type || "-"}`,
                    `Blocker: ${s.blocker_reason || "-"}`,
                  ],
                  target_type: 'step',
                  target_id: s.id || '',
                  campaign_id: s.campaign_id || ws.campaign.id || '',
                  open_deep_link: campaignsPathWithTarget({ targetType: 'step', targetId: s.id || '', campaignId: s.campaign_id || ws.campaign.id || '', expand: 'work' }),
                  open_path: '/campaigns',
                  open_label: "Open Campaigns",
                })}")'>Details</button>
              </div>
            `;
          }).join('');
          return `
            <details class='ops-accordion surface-2'>
              <summary>
                ${parentTitle} · Steps ${steps.length} · Planned ${counts.planned} · Active ${counts.active} · Done ${counts.done}
              </summary>
              <div style='padding:0 10px 10px 10px;'>
                <div class='queue-list'>${cards || "<div class='sub'>No steps.</div>"}</div>
              </div>
            </details>
          `;
        }).join('');
        body.innerHTML = accordionHtml || "<div class='sub'>No tasks for this campaign.</div>";
        return;
      }
      if (currentWorkspaceTab === 'reviews') {
        body.innerHTML = workspaceTable(
          ['When', 'Type', 'Status', 'Comment'],
          ws.reviews.recent.map(r => `<tr><td>${niceDate(r.created_at)}</td><td>${r.review_type}</td><td>${statusChip(r.status)}</td><td>${r.comments || '-'}</td></tr>`).join('')
        );
        return;
      }
      if (currentWorkspaceTab === 'risks') {
        const rows = [
          ...ws.risks.system.map(r => `<tr><td>System</td><td>${r.id}</td><td>${r.severity}</td><td>${r.code}</td><td>${r.details}</td></tr>`),
          ...ws.risks.manual.map(r => `<tr><td>Manual</td><td>${r.id}</td><td>${r.severity}</td><td>-</td><td>${r.details}</td></tr>`),
        ].join('');
        body.innerHTML = workspaceTable(['Type', 'ID', 'Severity', 'Code', 'Details'], rows);
        return;
      }
      if (currentWorkspaceTab === 'timeline') {
        const checkpoints = (ws.health_summary?.checkpoint_health || []).map(cp => `
          <tr>
            <td>
              <button class='ghost' onclick='openItemPopoverByPayload(this, "${encodePopoverPayload({
                title: cp.step_name || cp.step_id || "Timeline checkpoint",
                module_type: "step",
                step: {
                  id: cp.step_id || '',
                  name: cp.step_name || cp.step_id || 'Step',
                  campaign_id: ws.campaign?.id || '',
                  deliverable_id: cp.deliverable_id || null,
                  current_due: cp.current_due || null,
                  waiting_on_type: cp.waiting_on_type || null,
                  blocker_reason: cp.blocker_reason || null,
                },
                campaign: { id: ws.campaign?.id || '', title: ws.campaign?.title || '-' },
                deliverable: { id: cp.deliverable_id || null, title: cp.deliverable_id || '-' },
                details: [
                  `Step ID: ${cp.step_id || "-"}`,
                  `Deliverable: ${cp.deliverable_id || "-"}`,
                  `Health: ${cp.status || "not_started"}`,
                  `Due: ${cp.current_due || "-"}`,
                  `Waiting on: ${cp.waiting_on_type || "-"}`,
                  `Blocker: ${cp.blocker_reason || "-"}`,
                ],
                target_type: 'step',
                target_id: cp.step_id || '',
                campaign_id: ws.campaign?.id || '',
                open_deep_link: campaignsPathWithTarget({ targetType: 'step', targetId: cp.step_id || '', campaignId: ws.campaign?.id || '', expand: 'work' }),
                open_path: '/campaigns',
                open_label: "Open Campaigns",
              })}")'>${cp.step_id || '-'}</button>
            </td>
            <td>${cp.step_name || '-'}</td>
            <td>${cp.deliverable_id || '-'}</td>
            <td>${healthChip(cp.status || 'not_started')}</td>
            <td>${cp.current_due || '-'}</td>
            <td>${cp.waiting_on_type || '-'}</td>
            <td>${cp.blocker_reason || '-'}</td>
          </tr>
        `).join('');
        const milestones = ws.timeline.milestones.map(m => `<tr>
          <td>
            <button class='ghost' onclick='openItemPopoverByPayload(this, "${encodePopoverPayload({
              title: m.name || m.id || "Milestone",
              module_type: "campaign",
              campaign: { id: ws.campaign?.id || '', title: ws.campaign?.title || '-' },
              details: [
                `Milestone ID: ${m.id || "-"}`,
                `Baseline: ${m.baseline_date || "-"}`,
                `Current target: ${m.current_target_date || "-"}`,
                `Achieved: ${m.achieved_at || "-"}`,
              ],
              target_type: 'campaign',
              target_id: ws.campaign?.id || '',
              campaign_id: ws.campaign?.id || '',
              open_deep_link: campaignsPathWithTarget({ targetType: 'campaign', targetId: ws.campaign?.id || '', campaignId: ws.campaign?.id || '' }),
              open_path: '/campaigns',
              open_label: "Open Campaigns",
            })}")'>${m.id}</button>
          </td>
          <td>${m.name}</td>
          <td>${m.baseline_date || '-'}</td>
          <td>${m.current_target_date || '-'}</td>
          <td>${niceDate(m.achieved_at)}</td>
        </tr>`).join('');
        body.innerHTML = `
          ${workspaceTable(['Step ID', 'Checkpoint', 'Deliverable', 'Health', 'Current Due', 'Waiting On', 'Blocker'], checkpoints)}
          <div class='spacer-md'></div>
          ${workspaceTable(['ID', 'Milestone', 'Baseline', 'Current', 'Achieved'], milestones)}
        `;
        return;
      }
      body.innerHTML = workspaceTable(
        ['When', 'Action', 'Meta'],
        ws.activity.map(a => `<tr><td>${niceDate(a.created_at)}</td><td>${a.action}</td><td>${JSON.stringify(a.meta || {})}</td></tr>`).join('')
      );
    }

    async function saveWorkspaceTaskDue(stepId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        if (!canUseControl('manage_step', currentRole)) {
          throw new Error('You do not have permission to edit tasks');
        }
        const input = document.getElementById(`taskDue_${stepId}`);
        const rawValue = (input?.value || '').trim();
        const ownerEl = document.getElementById(`taskOwner_${stepId}`);
        const actionEl = document.getElementById(`taskAction_${stepId}`);
        const reasonEl = document.getElementById(`taskReason_${stepId}`);
        const dueIso = rawValue ? nextWorkingIsoFromIso(rawValue) : null;
        const result = await api(`/api/workflow-steps/${stepId}/manage`, {
          method: 'PATCH',
          body: JSON.stringify({
            actor_user_id: currentActorId,
            status: actionEl?.value || 'in_progress',
            next_owner_user_id: ownerEl?.value || null,
            waiting_on_user_id: null,
            blocker_reason: reasonEl?.value || null,
            current_due_iso: dueIso,
          }),
        });
        log('Task updated', result);
        const effective = String(result.current_due || dueIso || '').slice(0, 10);
        if (input) input.value = effective;
        toast(`Task saved${effective ? ` · Due ${effective}` : ''}`, 'success');
        workspaceCache = null;
        await Promise.all([renderCampaignWorkspace(), renderMyWork(currentRole, currentActorId), renderCapacity()]);
      } catch (err) {
        toast(`Unable to save task: ${String(err)}`, 'error');
        log('Update task failed', String(err));
      }
    }

    async function renderReviewsQueue() {
      if (!currentActorId || !currentRole) return;
      const data = await api(`/api/reviews/queue?actor_user_id=${currentActorId}&role=${currentRole}`);
      const body = document.getElementById('reviewsQueueBody');
      const rows = [];
      const order = ['awaiting_internal_review', 'awaiting_client_review', 'changes_requested'];
      for (const key of order) {
        for (const item of (data.queues[key] || [])) {
          rows.push(`
            <tr>
              <td>${item.window_type || key}</td>
              <td>Round ${item.round_number || 1}</td>
              <td>${item.deliverable_title}</td>
              <td>${item.campaign_id || '-'}</td>
              <td>${item.window_due || '-'}</td>
              <td><button onclick="selectDeliverableForHistory('${item.deliverable_id}')">Open</button></td>
            </tr>
          `);
        }
      }
      body.innerHTML = rows.join('') || `<tr><td colspan='6' class='sub'>No review items.</td></tr>`;
      document.getElementById('reviewsSummary').textContent = `Internal ${data.summary.awaiting_internal_review} · Client ${data.summary.awaiting_client_review} · Changes ${data.summary.changes_requested}`;
    }

    async function renderWorkflowSteps() {
      const data = await api('/api/workflow-steps');
      const body = document.getElementById('stepsBody');
      body.innerHTML = data.items.slice(0, 20).map(s => `
        <tr>
          <td>${s.name}</td>
          <td>${s.owner_role}</td>
          <td>${niceDate(s.current_due)}</td>
          <td>${s.actual_done ? 'Yes' : 'No'}</td>
          <td><code>${s.id}</code></td>
        </tr>
      `).join('') || `<tr><td colspan='5' class='sub'>No steps yet.</td></tr>`;
      document.getElementById('stepsCount').textContent = `${Math.min(data.items.length, 20)} shown / ${data.items.length} total`;
      return data.items;
    }

    async function renderMilestones() {
      const data = await api('/api/milestones');
      const body = document.getElementById('milestonesBody');
      body.innerHTML = data.items.slice(0, 30).map(m => `
        <tr>
          <td><code>${m.id}</code></td>
          <td>${m.name}</td>
          <td>${m.baseline_date || '-'}</td>
          <td>${m.current_target_date || '-'}</td>
          <td>${niceDate(m.achieved_at)}</td>
        </tr>
      `).join('') || `<tr><td colspan='5' class='sub'>No milestones yet.</td></tr>`;
      document.getElementById('milestonesCount').textContent = `${Math.min(data.items.length, 30)} shown / ${data.items.length} total`;
      return data.items;
    }

    async function renderOpsDefaults() {
      if (!currentActorId) return;
      const card = document.getElementById('sectionOpsDefaults');
      if (!card) return;
      if (!(currentRole === 'head_ops' || currentRole === 'admin')) {
        card.classList.add('hidden');
        return;
      }
      card.classList.remove('hidden');
      const data = await api(`/api/admin/ops-defaults?actor_user_id=${currentActorId}`);
      opsDefaultsCache = data.defaults || {};
      CARD_MODULE_CONFIG = normalizeCardModuleConfig((opsDefaultsCache || {}).card_module_config || {});
      CARD_MODULE_BINDINGS = normalizeCardModuleBindings((opsDefaultsCache || {}).card_module_bindings || {});
      LIST_MODULE_CONFIG = normalizeListModuleConfig((opsDefaultsCache || {}).list_module_config || {});
      LIST_MODULE_BINDINGS = normalizeListModuleBindings((opsDefaultsCache || {}).list_module_bindings || {});

      const cap = opsDefaultsCache.capacity_hours_per_week || {};
      const timeline = opsDefaultsCache.timeline_defaults || {};
      const workload = opsDefaultsCache.content_workload_hours || {};
      const buffers = opsDefaultsCache.health_buffer_days || {};
      const progressOrder = normalizeProgressSegmentOrder(opsDefaultsCache.progress_segment_order || DEFAULT_PROGRESS_SEGMENT_ORDER);
      PROGRESS_SEGMENT_ORDER = [...progressOrder];
      const stepBuffer = buffers.step || {};
      const deliverableBuffer = buffers.deliverable || {};
      const campaignBuffer = buffers.campaign || {};
      const scopeBuffer = buffers.scope || {};
      const setVal = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.value = String(value ?? '');
      };
      setVal('opsWorkKoPrep', workload.ko_prep_hours);
      setVal('opsWorkContentPlan', workload.content_plan_hours);
      setVal('opsWorkInterview', workload.interview_hours);
      setVal('opsWorkArticle', workload.article_drafting_hours);
      setVal('opsWorkVideoBrief', workload.video_brief_hours);
      setVal('opsWorkAmends', workload.amends_reserve_hours);
      setVal('opsCapAm', cap.am);
      setVal('opsCapCm', cap.cm);
      setVal('opsCapCc', cap.cc);
      setVal('opsCapDn', (cap.dn ?? 16));
      setVal('opsCapMm', (cap.mm ?? 16));
      setVal('opsTimelineInterviewWeeks', timeline.interview_weeks_after_ko);
      setVal('opsTimelineWriting', timeline.writing_working_days);
      setVal('opsTimelineInternalReview', timeline.internal_review_working_days);
      setVal('opsTimelineClientReview', timeline.client_review_working_days);
      setVal('opsTimelinePublish', timeline.publish_after_client_review_working_days);
      setVal('opsTimelinePromotion', timeline.promotion_duration_calendar_days);
      setVal('opsTimelineReporting', timeline.reporting_duration_calendar_days);
      setVal('opsHealthStepDefault', stepBuffer.default ?? 3);
      setVal('opsHealthDeliverablePlanning', deliverableBuffer.planning ?? 20);
      setVal('opsHealthDeliverableProduction', deliverableBuffer.production ?? 12);
      setVal('opsHealthDeliverablePromotion', deliverableBuffer.promotion ?? 8);
      setVal('opsHealthDeliverableReporting', deliverableBuffer.reporting ?? 8);
      setVal('opsHealthCampaignDefault', campaignBuffer.default ?? 12);
      setVal('opsHealthScopeDefault', scopeBuffer.default ?? 24);
      const progressSelectIds = [
        'opsProgressOrder1', 'opsProgressOrder2', 'opsProgressOrder3', 'opsProgressOrder4',
        'opsProgressOrder5', 'opsProgressOrder6', 'opsProgressOrder7', 'opsProgressOrder8',
      ];
      const progressSelectOptions = GLOBAL_STATUS_OPTIONS.map(opt => `<option value='${opt.value}'>${opt.label}</option>`).join('');
      progressSelectIds.forEach((id, idx) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = progressSelectOptions;
        el.value = progressOrder[idx] || DEFAULT_PROGRESS_SEGMENT_ORDER[idx];
      });
    }

    async function renderCardModuleSettings() {
      const card = document.getElementById('sectionCardModules');
      const body = document.getElementById('cardModulesBody');
      const meta = document.getElementById('cardModulesMeta');
      if (!card || !body || !meta) return;
      const isSuperadmin = String(currentActorIdentity?.app_role || '').toLowerCase() === 'superadmin';
      if (!isSuperadmin) {
        card.classList.add('hidden');
        return;
      }
      card.classList.remove('hidden');
      if (!opsDefaultsCache) {
        const data = await api(`/api/admin/ops-defaults?actor_user_id=${currentActorId}`);
        opsDefaultsCache = data.defaults || {};
      }
      CARD_MODULE_CONFIG = normalizeCardModuleConfig((opsDefaultsCache || {}).card_module_config || {});
      CARD_MODULE_BINDINGS = normalizeCardModuleBindings((opsDefaultsCache || {}).card_module_bindings || {});
      LIST_MODULE_CONFIG = normalizeListModuleConfig((opsDefaultsCache || {}).list_module_config || {});
      LIST_MODULE_BINDINGS = normalizeListModuleBindings((opsDefaultsCache || {}).list_module_bindings || {});
      meta.textContent = 'Choose which fields are shown for each module card type.';
      const moduleLabel = {
        scope: 'Scope',
        campaign: 'Campaign',
        deliverable: 'Deliverable',
        stage: 'Stage',
        step: 'Step',
      };
      const GROUP_LABELS = {
        header: 'Header',
        body: 'Body',
        footer: 'Footer',
      };
      const MODULE_SLOT_META = {
        scope: {
          subtitle: { group: 'header', format: 'text' },
          description: { group: 'body', format: 'text' },
          progress: { group: 'body', format: 'progress bar' },
          key_values: { group: 'body', format: 'key-value' },
          list: { group: 'body', format: 'accordion/list' },
          tags: { group: 'body', format: 'tag list' },
          status_badge: { group: 'footer', format: 'status badge' },
          avatar_stack: { group: 'footer', format: 'avatar stack' },
          due_date: { group: 'footer', format: 'date' },
          actions: { group: 'footer', format: 'action buttons' },
          scope_status: { group: 'header', format: 'status pill' },
          scope_health: { group: 'header', format: 'health pill' },
          timeframe: { group: 'header', format: 'date range' },
          scope_id: { group: 'header', format: 'code/id' },
          brand_name: { group: 'body', format: 'text' },
          am_owner: { group: 'body', format: 'user pill' },
          client_contact: { group: 'body', format: 'text' },
          products: { group: 'body', format: 'tag list' },
          sow_attachment: { group: 'body', format: 'link' },
          campaigns: { group: 'body', format: 'accordion' },
          icp: { group: 'body', format: 'accordion' },
          objective: { group: 'body', format: 'accordion' },
          messaging: { group: 'body', format: 'accordion' },
        },
        campaign: {
          subtitle: { group: 'header', format: 'text' },
          description: { group: 'body', format: 'text' },
          progress: { group: 'body', format: 'progress bar' },
          key_values: { group: 'body', format: 'key-value' },
          list: { group: 'body', format: 'accordion/list' },
          tags: { group: 'body', format: 'tag list' },
          status_badge: { group: 'footer', format: 'status badge' },
          avatar_stack: { group: 'footer', format: 'avatar stack' },
          due_date: { group: 'footer', format: 'date' },
          actions: { group: 'footer', format: 'action buttons' },
          campaign_status: { group: 'header', format: 'status pill' },
          campaign_health: { group: 'header', format: 'health pill' },
          timeframe: { group: 'header', format: 'date range' },
          owner: { group: 'header', format: 'user pill' },
          demand_track: { group: 'header', format: 'text' },
          campaign_id: { group: 'header', format: 'code/id' },
          users_assigned: { group: 'body', format: 'user list' },
          scope_id: { group: 'body', format: 'code/id' },
          deliverables: { group: 'body', format: 'accordion' },
          work: { group: 'body', format: 'list' },
        },
        deliverable: {
          subtitle: { group: 'header', format: 'text' },
          description: { group: 'body', format: 'text' },
          progress: { group: 'body', format: 'progress bar' },
          key_values: { group: 'body', format: 'key-value' },
          list: { group: 'body', format: 'list' },
          tags: { group: 'body', format: 'tag list' },
          status_badge: { group: 'footer', format: 'status badge' },
          avatar_stack: { group: 'footer', format: 'avatar stack' },
          due_date: { group: 'footer', format: 'date' },
          actions: { group: 'footer', format: 'action buttons' },
          deliverable_status: { group: 'header', format: 'status pill' },
          timeframe: { group: 'header', format: 'date range' },
          owner: { group: 'header', format: 'user pill' },
          stage: { group: 'header', format: 'tag/text' },
          campaign_id: { group: 'header', format: 'code/id' },
          campaign_name: { group: 'body', format: 'text' },
          deliverable_id: { group: 'body', format: 'code/id' },
        },
        stage: {
          subtitle: { group: 'header', format: 'text' },
          description: { group: 'body', format: 'text' },
          progress: { group: 'body', format: 'progress bar' },
          key_values: { group: 'body', format: 'key-value' },
          list: { group: 'body', format: 'list' },
          tags: { group: 'body', format: 'tag list' },
          status_badge: { group: 'footer', format: 'status badge' },
          avatar_stack: { group: 'footer', format: 'avatar stack' },
          due_date: { group: 'footer', format: 'date' },
          actions: { group: 'footer', format: 'action buttons' },
          stage_status: { group: 'header', format: 'status pill' },
          stage_health: { group: 'header', format: 'health pill' },
          timeframe: { group: 'header', format: 'date range' },
          campaign_id: { group: 'header', format: 'code/id' },
          campaign_name: { group: 'body', format: 'text' },
          stage_id: { group: 'body', format: 'code/id' },
          steps: { group: 'body', format: 'accordion/list' },
        },
        step: {
          subtitle: { group: 'header', format: 'text' },
          description: { group: 'body', format: 'text' },
          progress: { group: 'body', format: 'progress bar' },
          key_values: { group: 'body', format: 'key-value' },
          list: { group: 'body', format: 'list' },
          tags: { group: 'body', format: 'tag list' },
          status_badge: { group: 'footer', format: 'status badge' },
          avatar_stack: { group: 'footer', format: 'avatar stack' },
          due_date: { group: 'footer', format: 'date' },
          actions: { group: 'footer', format: 'action buttons' },
          step_status: { group: 'header', format: 'status pill' },
          step_health: { group: 'header', format: 'health pill' },
          timeframe: { group: 'header', format: 'date range' },
          owner: { group: 'header', format: 'user pill' },
          stage: { group: 'header', format: 'text/tag' },
          campaign_id: { group: 'header', format: 'code/id' },
          step_id: { group: 'body', format: 'code/id' },
          assigned_users: { group: 'body', format: 'user pills' },
          campaign_ref: { group: 'body', format: 'text' },
          linked_deliverable: { group: 'body', format: 'text' },
          note: { group: 'body', format: 'text input' },
        },
      };
      function optionMeta(moduleType, key) {
        const mod = MODULE_SLOT_META[String(moduleType || '').toLowerCase()] || {};
        return mod[key] || { group: 'body', format: 'field' };
      }
      function hasBindingDropdown(moduleType, slotKey) {
        const allowed = CARD_MODULE_BINDING_OPTIONS?.[moduleType]?.[slotKey];
        return Array.isArray(allowed) && allowed.length > 1;
      }
      function bindingOptionsFor(moduleType, slotKey) {
        const allowedKeys = CARD_MODULE_BINDING_OPTIONS?.[moduleType]?.[slotKey] || [];
        const labels = Object.fromEntries((MODULE_FIELD_OPTIONS[moduleType] || []).map(o => [o.key, o.label || o.key]));
        return allowedKeys
          .map(key => ({ key, label: labels[key] || key }))
          .filter(item => item.key);
      }
      function isKeyValueCandidate(moduleType, optionKey) {
        const key = String(optionKey || '');
        if (!key || MODULE_STRUCTURAL_KEYS.has(key)) return false;
        const meta = optionMeta(moduleType, key);
        const fmt = String(meta.format || '').toLowerCase();
        if (fmt.includes('accordion')) return false;
        if (fmt === 'tag list') return false;
        if (fmt === 'action buttons') return false;
        return true;
      }
      const rows = Object.keys(DEFAULT_CARD_MODULE_CONFIG).map(moduleType => {
        const options = MODULE_FIELD_OPTIONS[moduleType] || [];
        const grouped = { header: [], body: [], footer: [] };
        for (const option of options) {
          const g = optionMeta(moduleType, option.key).group;
          if (!grouped[g]) grouped[g] = [];
          grouped[g].push(option);
        }
        const checksByGroup = Object.entries(grouped).map(([groupKey, groupOptions]) => {
          if (!groupOptions.length) return '';
          const keyValueOptions = (MODULE_FIELD_OPTIONS[moduleType] || []).filter(opt => isKeyValueCandidate(moduleType, opt.key));
          const keyValueOptionKeys = new Set(keyValueOptions.map(opt => String(opt.key || '')));
          const checks = groupOptions.map(option => {
            const slotKey = option.key;
            if (slotKey !== 'key_values' && keyValueOptionKeys.has(String(slotKey || ''))) return '';
            const checked = !!CARD_MODULE_CONFIG?.[moduleType]?.[slotKey];
            const formatLabel = optionMeta(moduleType, slotKey).format;
            const currentBinding = String(CARD_MODULE_BINDINGS?.[moduleType]?.[slotKey] || slotKey);
            const showDropdown = hasBindingDropdown(moduleType, slotKey);
            const selectOptions = showDropdown
              ? [
                  ...bindingOptionsFor(moduleType, slotKey).map(src => {
                    const selected = currentBinding === src.key ? 'selected' : '';
                    return `<option value='${src.key}' ${selected}>${src.label}</option>`;
                  }),
                ].join('')
              : '';
            const keyValueList = slotKey === 'key_values'
              ? `
                <div style='margin:8px 0 0 26px;'>
                  <div class='sub' style='margin-bottom:6px;'>Key-value fields</div>
                  <div class='perm-dim-group'>
                    ${keyValueOptions.map(kv => {
                      const kvKey = String(kv.key || '');
                      const kvChecked = !!CARD_MODULE_CONFIG?.[moduleType]?.[kvKey];
                      const kvFormat = optionMeta(moduleType, kvKey).format;
                      return `<label class='perm-opt'>` +
                        `<input type='checkbox' data-card-module='${moduleType}' data-card-slot='${kvKey}' ${kvChecked ? 'checked' : ''} />` +
                        `<span>${kv.label || kvKey} <span class='sub' style='display:inline; margin-left:6px;'>(${kvFormat})</span></span>` +
                      `</label>`;
                    }).join('')}
                  </div>
                </div>
              `
              : '';
            return `<label class='perm-opt'>` +
              `<input type='checkbox' data-card-module='${moduleType}' data-card-slot='${slotKey}' ${checked ? 'checked' : ''} />` +
              `<span>${option.label || slotKey} <span class='sub' style='display:inline; margin-left:6px;'>(${formatLabel})</span></span>` +
              `${showDropdown ? `<select data-card-module='${moduleType}' data-card-binding='${slotKey}' style='min-width:220px; margin-left:auto;'>${selectOptions}</select>` : ''}` +
            `</label>` + keyValueList;
          }).join('');
          return `
            <div class='surface-2' style='padding:8px; border:0.5px solid var(--line); border-radius:8px;'>
              <div class='sub' style='margin-bottom:6px; font-weight:600;'>${GROUP_LABELS[groupKey] || groupKey}</div>
              <div class='perm-dim-group'>${checks}</div>
            </div>
          `;
        }).join('');
        return `
          <details class='ops-accordion surface-2'>
            <summary>${moduleLabel[moduleType] || moduleType} card</summary>
            <div style='padding:8px 10px;'>
              <div style='display:grid; gap:8px;'>${checksByGroup}</div>
            </div>
          </details>
        `;
      }).join('');
      body.innerHTML = rows || "<div class='sub'>No module settings found.</div>";
    }

    async function renderListModuleSettings() {
      const card = document.getElementById('sectionListModules');
      const body = document.getElementById('listModulesBody');
      const meta = document.getElementById('listModulesMeta');
      if (!card || !body || !meta) return;
      const isSuperadmin = String(currentActorIdentity?.app_role || '').toLowerCase() === 'superadmin';
      if (!isSuperadmin) {
        card.classList.add('hidden');
        return;
      }
      card.classList.remove('hidden');
      if (!opsDefaultsCache) {
        const data = await api(`/api/admin/ops-defaults?actor_user_id=${currentActorId}`);
        opsDefaultsCache = data.defaults || {};
      }
      LIST_MODULE_CONFIG = normalizeListModuleConfig((opsDefaultsCache || {}).list_module_config || {});
      LIST_MODULE_BINDINGS = normalizeListModuleBindings((opsDefaultsCache || {}).list_module_bindings || {});
      meta.textContent = 'Configure list row elements and field mappings by object type.';
      const moduleLabel = { scope: 'Scope', campaign: 'Campaign', deliverable: 'Deliverable', stage: 'Stage', step: 'Step' };
      const groupLabel = { left: 'Left section', middle: 'Middle section', right: 'Right section' };

      function canBind(moduleType, slotKey) {
        const allowed = LIST_MODULE_BINDING_OPTIONS?.[moduleType]?.[slotKey];
        return Array.isArray(allowed) && allowed.length > 1;
      }
      function bindOptions(moduleType, slotKey) {
        const allowed = LIST_MODULE_BINDING_OPTIONS?.[moduleType]?.[slotKey] || [];
        return allowed.map(opt => ({ key: opt, label: toTitle(String(opt).replace(/_/g, ' ')) }));
      }

      const rows = Object.keys(DEFAULT_LIST_MODULE_CONFIG).map(moduleType => {
        const options = LIST_FIELD_OPTIONS[moduleType] || [];
        const groups = { left: [], middle: [], right: [] };
        for (const option of options) {
          const g = String(option.group || 'middle').toLowerCase();
          if (!groups[g]) groups[g] = [];
          groups[g].push(option);
        }
        const groupHtml = Object.keys(groups).map(g => {
          const opts = groups[g] || [];
          if (!opts.length) return '';
          const checks = opts.map(option => {
            const slotKey = String(option.key || '');
            const checked = !!LIST_MODULE_CONFIG?.[moduleType]?.[slotKey];
            const formatLabel = option.format || 'field';
            const currentBinding = String(LIST_MODULE_BINDINGS?.[moduleType]?.[slotKey] || slotKey);
            const showDropdown = canBind(moduleType, slotKey);
            const selectOptions = showDropdown
              ? bindOptions(moduleType, slotKey).map(src => `<option value='${src.key}' ${currentBinding === src.key ? 'selected' : ''}>${src.label}</option>`).join('')
              : '';
            return `<label class='perm-opt'>` +
              `<input type='checkbox' data-list-module='${moduleType}' data-list-slot='${slotKey}' ${checked ? 'checked' : ''} />` +
              `<span>${option.label || slotKey} <span class='sub' style='display:inline; margin-left:6px;'>(${formatLabel})</span></span>` +
              `${showDropdown ? `<select data-list-module='${moduleType}' data-list-binding='${slotKey}' style='min-width:220px; margin-left:auto;'>${selectOptions}</select>` : ''}` +
            `</label>`;
          }).join('');
          return `
            <div class='surface-2' style='padding:8px; border:0.5px solid var(--line); border-radius:8px;'>
              <div class='sub' style='margin-bottom:6px; font-weight:600;'>${groupLabel[g] || g}</div>
              <div class='perm-dim-group'>${checks}</div>
            </div>
          `;
        }).join('');
        return `
          <details class='ops-accordion surface-2'>
            <summary>${moduleLabel[moduleType] || moduleType} list rows</summary>
            <div style='padding:8px 10px; display:grid; gap:8px;'>${groupHtml}</div>
          </details>
        `;
      }).join('');
      body.innerHTML = rows || "<div class='sub'>No list module settings found.</div>";
    }

    async function saveOpsDefaults(event) {
      if (event) event.preventDefault();
      if (!currentActorId) return;
      try {
        const payload = {
          content_workload_hours: {
            ko_prep_hours: Number(document.getElementById('opsWorkKoPrep')?.value || 0),
            content_plan_hours: Number(document.getElementById('opsWorkContentPlan')?.value || 0),
            interview_hours: Number(document.getElementById('opsWorkInterview')?.value || 0),
            article_drafting_hours: Number(document.getElementById('opsWorkArticle')?.value || 0),
            video_brief_hours: Number(document.getElementById('opsWorkVideoBrief')?.value || 0),
            amends_reserve_hours: Number(document.getElementById('opsWorkAmends')?.value || 0),
          },
          capacity_hours_per_week: {
            am: Number(document.getElementById('opsCapAm')?.value || 0),
            cm: Number(document.getElementById('opsCapCm')?.value || 0),
            cc: Number(document.getElementById('opsCapCc')?.value || 0),
            dn: Number(document.getElementById('opsCapDn')?.value || 0),
            mm: Number(document.getElementById('opsCapMm')?.value || 0),
          },
          timeline_defaults: {
            interview_weeks_after_ko: Number(document.getElementById('opsTimelineInterviewWeeks')?.value || 0),
            writing_working_days: Number(document.getElementById('opsTimelineWriting')?.value || 0),
            internal_review_working_days: Number(document.getElementById('opsTimelineInternalReview')?.value || 0),
            client_review_working_days: Number(document.getElementById('opsTimelineClientReview')?.value || 0),
            publish_after_client_review_working_days: Number(document.getElementById('opsTimelinePublish')?.value || 0),
            promotion_duration_calendar_days: Number(document.getElementById('opsTimelinePromotion')?.value || 0),
            reporting_duration_calendar_days: Number(document.getElementById('opsTimelineReporting')?.value || 0),
          },
          health_buffer_days: {
            step: {
              default: Number(document.getElementById('opsHealthStepDefault')?.value || 0),
            },
            deliverable: {
              planning: Number(document.getElementById('opsHealthDeliverablePlanning')?.value || 0),
              production: Number(document.getElementById('opsHealthDeliverableProduction')?.value || 0),
              promotion: Number(document.getElementById('opsHealthDeliverablePromotion')?.value || 0),
              reporting: Number(document.getElementById('opsHealthDeliverableReporting')?.value || 0),
              default: Number(document.getElementById('opsHealthDeliverableProduction')?.value || 0),
            },
            campaign: {
              default: Number(document.getElementById('opsHealthCampaignDefault')?.value || 0),
            },
            scope: {
              default: Number(document.getElementById('opsHealthScopeDefault')?.value || 0),
            },
          },
          progress_segment_order: normalizeProgressSegmentOrder([
            document.getElementById('opsProgressOrder1')?.value,
            document.getElementById('opsProgressOrder2')?.value,
            document.getElementById('opsProgressOrder3')?.value,
            document.getElementById('opsProgressOrder4')?.value,
            document.getElementById('opsProgressOrder5')?.value,
            document.getElementById('opsProgressOrder6')?.value,
            document.getElementById('opsProgressOrder7')?.value,
            document.getElementById('opsProgressOrder8')?.value,
          ]),
        };
        const result = await api(`/api/admin/ops-defaults?actor_user_id=${currentActorId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
        opsDefaultsCache = result.defaults || payload;
        PROGRESS_SEGMENT_ORDER = normalizeProgressSegmentOrder((opsDefaultsCache || {}).progress_segment_order || DEFAULT_PROGRESS_SEGMENT_ORDER);
        toast('Ops defaults updated', 'success');
        log('Ops defaults updated', result);
      } catch (err) {
        log('Update ops defaults failed', String(err));
      }
    }

    async function saveCardModuleSettings(event) {
      if (event) event.preventDefault();
      if (!currentActorId) return;
      if (String(currentActorIdentity?.app_role || '').toLowerCase() !== 'superadmin') {
        toast('Only Superadmin can edit card module settings', 'error');
        return;
      }
      try {
        const nextCfg = normalizeCardModuleConfig(CARD_MODULE_CONFIG || {});
        const nextBindings = normalizeCardModuleBindings(CARD_MODULE_BINDINGS || {});
        document.querySelectorAll('#cardModulesBody input[type="checkbox"][data-card-module][data-card-slot]').forEach(el => {
          const moduleType = String(el.getAttribute('data-card-module') || '').toLowerCase();
          const slotKey = String(el.getAttribute('data-card-slot') || '');
          if (!nextCfg[moduleType] || !Object.prototype.hasOwnProperty.call(nextCfg[moduleType], slotKey)) return;
          nextCfg[moduleType][slotKey] = !!el.checked;
        });
        document.querySelectorAll('#cardModulesBody select[data-card-module][data-card-binding]').forEach(el => {
          const moduleType = String(el.getAttribute('data-card-module') || '').toLowerCase();
          const slotKey = String(el.getAttribute('data-card-binding') || '');
          const sourceKey = String(el.value || slotKey).trim();
          if (!moduleType || !slotKey) return;
          if (!nextBindings[moduleType]) nextBindings[moduleType] = {};
          nextBindings[moduleType][slotKey] = sourceKey || slotKey;
        });
        const result = await api(`/api/admin/ops-defaults?actor_user_id=${currentActorId}`, {
          method: 'PUT',
          body: JSON.stringify({ card_module_config: nextCfg, card_module_bindings: nextBindings }),
        });
        opsDefaultsCache = result.defaults || opsDefaultsCache || {};
        CARD_MODULE_CONFIG = normalizeCardModuleConfig((opsDefaultsCache || {}).card_module_config || nextCfg);
        CARD_MODULE_BINDINGS = normalizeCardModuleBindings((opsDefaultsCache || {}).card_module_bindings || nextBindings);
        LIST_MODULE_CONFIG = normalizeListModuleConfig((opsDefaultsCache || {}).list_module_config || LIST_MODULE_CONFIG);
        LIST_MODULE_BINDINGS = normalizeListModuleBindings((opsDefaultsCache || {}).list_module_bindings || LIST_MODULE_BINDINGS);
        toast('Card module settings updated', 'success');
        await renderScreen();
      } catch (err) {
        toast(`Unable to save card settings: ${String(err)}`, 'error');
      }
    }

    async function saveListModuleSettings(event) {
      if (event) event.preventDefault();
      if (!currentActorId) return;
      if (String(currentActorIdentity?.app_role || '').toLowerCase() !== 'superadmin') {
        toast('Only Superadmin can edit list module settings', 'error');
        return;
      }
      try {
        const nextCfg = normalizeListModuleConfig(LIST_MODULE_CONFIG || {});
        const nextBindings = normalizeListModuleBindings(LIST_MODULE_BINDINGS || {});
        document.querySelectorAll('#listModulesBody input[type="checkbox"][data-list-module][data-list-slot]').forEach(el => {
          const moduleType = String(el.getAttribute('data-list-module') || '').toLowerCase();
          const slotKey = String(el.getAttribute('data-list-slot') || '');
          if (!nextCfg[moduleType] || !Object.prototype.hasOwnProperty.call(nextCfg[moduleType], slotKey)) return;
          nextCfg[moduleType][slotKey] = !!el.checked;
        });
        document.querySelectorAll('#listModulesBody select[data-list-module][data-list-binding]').forEach(el => {
          const moduleType = String(el.getAttribute('data-list-module') || '').toLowerCase();
          const slotKey = String(el.getAttribute('data-list-binding') || '');
          const sourceKey = String(el.value || slotKey).trim();
          if (!moduleType || !slotKey) return;
          if (!nextBindings[moduleType]) nextBindings[moduleType] = {};
          nextBindings[moduleType][slotKey] = sourceKey || slotKey;
        });
        const result = await api(`/api/admin/ops-defaults?actor_user_id=${currentActorId}`, {
          method: 'PUT',
          body: JSON.stringify({ list_module_config: nextCfg, list_module_bindings: nextBindings }),
        });
        opsDefaultsCache = result.defaults || opsDefaultsCache || {};
        LIST_MODULE_CONFIG = normalizeListModuleConfig((opsDefaultsCache || {}).list_module_config || nextCfg);
        LIST_MODULE_BINDINGS = normalizeListModuleBindings((opsDefaultsCache || {}).list_module_bindings || nextBindings);
        toast('List module settings updated', 'success');
        await renderScreen();
      } catch (err) {
        toast(`Unable to save list settings: ${String(err)}`, 'error');
      }
    }

    async function loadRolePermissions() {
      if (!currentActorId) return null;
      const payload = await api(`/api/admin/role-permissions?actor_user_id=${currentActorId}`);
      const rolePermissions = payload.role_permissions || {};
      const identityPermissions = payload.identity_permissions || {};
      const legacyControls = identityPermissions.control_permissions || {};
      roleFlagMatrix = rolePermissions.role_flags || {};
      CONTROL_ROLE_MAP = rolePermissions.control_permissions || CONTROL_ROLE_MAP;
      const campaignControls = identityPermissions.campaign_control_permissions
        || Object.fromEntries(
          Object.entries(legacyControls).filter(([controlId]) => !isAppControlId(controlId))
            .map(([controlId, rule]) => [controlId, {
              teams: Array.isArray(rule?.teams) ? rule.teams : [],
              seniorities: Array.isArray(rule?.seniorities) ? rule.seniorities : [],
            }]),
        );
      const appControls = identityPermissions.app_control_permissions
        || Object.fromEntries(
          Object.entries(legacyControls).filter(([controlId]) => isAppControlId(controlId))
            .map(([controlId, rule]) => [controlId, {
              seniorities: Array.isArray(rule?.seniorities) ? rule.seniorities : [],
              app_roles: Array.isArray(rule?.app_roles) ? rule.app_roles : [],
            }]),
        );
      IDENTITY_PERMISSIONS = {
        screen_flags: identityPermissions.screen_flags || {},
        campaign_control_permissions: campaignControls,
        app_control_permissions: appControls,
        control_permissions: legacyControls,
      };
      IDENTITY_PERMISSION_DIMS = {
        teams: payload.teams || IDENTITY_PERMISSION_DIMS.teams,
        seniorities: payload.seniorities || IDENTITY_PERMISSION_DIMS.seniorities,
        app_roles: payload.app_roles || IDENTITY_PERMISSION_DIMS.app_roles,
      };
      rolePermissionsEditableRoles = payload.editable_roles || rolePermissionsEditableRoles;
      return payload;
    }

    function permissionCheckbox(kind, key, dimension, value, checked) {
      const c = checked ? 'checked' : '';
      return `<input type='checkbox' data-perm-kind='${kind}' data-perm-key='${key}' data-perm-dim='${dimension}' data-perm-value='${value}' ${c} />`;
    }

    function permissionTable(headers, rows) {
      return `
        <table>
          <thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
          <tbody>${rows.join('')}</tbody>
        </table>
      `;
    }

    function identityRuleFor(kind, key) {
      let source = {};
      if (kind === 'screen_flag') source = IDENTITY_PERMISSIONS?.screen_flags || {};
      if (kind === 'control_campaign') source = IDENTITY_PERMISSIONS?.campaign_control_permissions || {};
      if (kind === 'control_app') source = IDENTITY_PERMISSIONS?.app_control_permissions || {};
      const rule = source[key] || {};
      if (kind === 'control_campaign') {
        return {
          teams: Array.isArray(rule.teams) ? rule.teams : [],
          seniorities: Array.isArray(rule.seniorities) ? rule.seniorities : [],
        };
      }
      if (kind === 'control_app') {
        return {
          seniorities: Array.isArray(rule.seniorities) ? rule.seniorities : [],
          app_roles: Array.isArray(rule.app_roles) ? rule.app_roles : [],
        };
      }
      return {
        teams: Array.isArray(rule.teams) ? rule.teams : [],
        seniorities: Array.isArray(rule.seniorities) ? rule.seniorities : [],
        app_roles: Array.isArray(rule.app_roles) ? rule.app_roles : [],
      };
    }

    function permissionDimGroup(kind, key, dim, values, selected, labelFn) {
      const items = (values || []).map(v => {
        const checked = Array.isArray(selected) && selected.includes(v);
        return `<label class='perm-opt'>${permissionCheckbox(kind, key, dim, v, checked)} <span>${labelFn(v)}</span></label>`;
      }).join('');
      return `<div class='perm-dim-group'>${items || "<span class='sub'>No options</span>"}</div>`;
    }

    async function renderRolePermissionsEditor() {
      const card = document.getElementById('sectionRolePermissions');
      const body = document.getElementById('rolePermissionsBody');
      const meta = document.getElementById('rolePermissionsMeta');
      if (!card || !body || !meta) return;
      if (!(currentRole === 'head_ops' || currentRole === 'admin')) {
        card.classList.add('hidden');
        return;
      }
      card.classList.remove('hidden');
      try {
        await loadRolePermissions();
      } catch (err) {
        body.innerHTML = `<div class='sub'>Unable to load role permissions: ${String(err)}</div>`;
        return;
      }

      const teams = IDENTITY_PERMISSION_DIMS.teams || [];
      const seniorities = IDENTITY_PERMISSION_DIMS.seniorities || [];
      const appRoles = IDENTITY_PERMISSION_DIMS.app_roles || [];
      const screenHeaders = ['Screen', 'Teams', 'Seniority', 'App role'];
      const screenRows = ROLE_FLAG_KEYS.map(flagKey => {
        const rule = identityRuleFor('screen_flag', flagKey);
        return `<tr>
          <td>${labelRoleFlag(flagKey)}</td>
          <td>${permissionDimGroup('screen_flag', flagKey, 'teams', teams, rule.teams, teamLabel)}</td>
          <td>${permissionDimGroup('screen_flag', flagKey, 'seniorities', seniorities, rule.seniorities, seniorityLabel)}</td>
          <td>${permissionDimGroup('screen_flag', flagKey, 'app_roles', appRoles, rule.app_roles, appRoleLabel)}</td>
        </tr>`;
      });

      const knownControlIds = Object.keys(CONTROL_ROLE_MAP || {}).sort((a, b) => a.localeCompare(b));
      const campaignControlIds = Array.from(
        new Set([
          ...Object.keys(IDENTITY_PERMISSIONS.campaign_control_permissions || {}),
          ...knownControlIds.filter(id => !isAppControlId(id)),
        ]),
      ).sort((a, b) => a.localeCompare(b));
      const appControlIds = Array.from(
        new Set([
          ...Object.keys(IDENTITY_PERMISSIONS.app_control_permissions || {}),
          ...knownControlIds.filter(id => isAppControlId(id)),
        ]),
      ).sort((a, b) => a.localeCompare(b));

      const campaignControlHeaders = ['Control', 'Teams', 'Seniority'];
      const campaignControlRows = campaignControlIds.map(controlId => {
        const rule = identityRuleFor('control_campaign', controlId);
        return `<tr>
          <td>${labelControl(controlId)}</td>
          <td>${permissionDimGroup('control_campaign', controlId, 'teams', teams, rule.teams, teamLabel)}</td>
          <td>${permissionDimGroup('control_campaign', controlId, 'seniorities', seniorities, rule.seniorities, seniorityLabel)}</td>
        </tr>`;
      });
      const appControlHeaders = ['Control', 'Seniority', 'App role'];
      const appControlRows = appControlIds.map(controlId => {
        const rule = identityRuleFor('control_app', controlId);
        return `<tr>
          <td>${labelControl(controlId)}</td>
          <td>${permissionDimGroup('control_app', controlId, 'seniorities', seniorities, rule.seniorities, seniorityLabel)}</td>
          <td>${permissionDimGroup('control_app', controlId, 'app_roles', appRoles, rule.app_roles, appRoleLabel)}</td>
        </tr>`;
      });

      body.innerHTML = `
        <details class='ops-accordion surface-2'>
          <summary>Screen access permissions (team/seniority/app role)</summary>
          <div style='padding:8px 10px;'>
            ${permissionTable(screenHeaders, screenRows)}
          </div>
        </details>
        <div class='spacer-md'></div>
        <details class='ops-accordion surface-2'>
          <summary>Campaign Control permissions (team/seniority)</summary>
          <div style='padding:8px 10px;'>
            ${permissionTable(campaignControlHeaders, campaignControlRows)}
          </div>
        </details>
        <div class='spacer-md'></div>
        <details class='ops-accordion surface-2'>
          <summary>App Control permissions (seniority/app role)</summary>
          <div style='padding:8px 10px;'>
            ${permissionTable(appControlHeaders, appControlRows)}
          </div>
        </details>
      `;
      meta.textContent = `Editing policy dimensions · ${ROLE_FLAG_KEYS.length} screen permissions · ${campaignControlIds.length} campaign controls · ${appControlIds.length} app controls`;
    }

    async function saveRolePermissions(event) {
      if (event) event.preventDefault();
      if (!currentActorId) return;
      try {
        const identityPayload = { screen_flags: {}, campaign_control_permissions: {}, app_control_permissions: {} };
        for (const flagKey of ROLE_FLAG_KEYS) {
          identityPayload.screen_flags[flagKey] = { teams: [], seniorities: [], app_roles: [] };
        }
        const campaignControlIds = Array.from(
          new Set([
            ...Object.keys(IDENTITY_PERMISSIONS.campaign_control_permissions || {}),
            ...Object.keys(CONTROL_ROLE_MAP || {}).filter(id => !isAppControlId(id)),
          ]),
        );
        const appControlIds = Array.from(
          new Set([
            ...Object.keys(IDENTITY_PERMISSIONS.app_control_permissions || {}),
            ...Object.keys(CONTROL_ROLE_MAP || {}).filter(id => isAppControlId(id)),
          ]),
        );
        for (const controlId of campaignControlIds) {
          identityPayload.campaign_control_permissions[controlId] = { teams: [], seniorities: [] };
        }
        for (const controlId of appControlIds) {
          identityPayload.app_control_permissions[controlId] = { seniorities: [], app_roles: [] };
        }

        document.querySelectorAll('#sectionRolePermissions input[data-perm-kind]').forEach(input => {
          const kind = input.getAttribute('data-perm-kind');
          const key = input.getAttribute('data-perm-key');
          const dim = input.getAttribute('data-perm-dim');
          const value = input.getAttribute('data-perm-value');
          if (!kind || !key || !dim || !value || !input.checked) return;
          const bucket = kind === 'screen_flag'
            ? identityPayload.screen_flags
            : (kind === 'control_campaign' ? identityPayload.campaign_control_permissions : identityPayload.app_control_permissions);
          if (!bucket[key]) {
            bucket[key] = kind === 'control_campaign'
              ? { teams: [], seniorities: [] }
              : (kind === 'control_app' ? { seniorities: [], app_roles: [] } : { teams: [], seniorities: [], app_roles: [] });
          }
          if (!Array.isArray(bucket[key][dim])) bucket[key][dim] = [];
          bucket[key][dim].push(value);
        });

        const roleFlags = roleFlagMatrix || {};
        const controls = CONTROL_ROLE_MAP || {};

        const result = await api(`/api/admin/role-permissions?actor_user_id=${currentActorId}`, {
          method: 'PUT',
          body: JSON.stringify({
            role_flags: roleFlags,
            control_permissions: controls,
            identity_permissions: identityPayload,
          }),
        });
        roleFlagMatrix = result.role_permissions?.role_flags || roleFlags;
        CONTROL_ROLE_MAP = result.role_permissions?.control_permissions || controls;
        IDENTITY_PERMISSIONS = result.identity_permissions || identityPayload;
        toast('Role permissions saved', 'success');
        await refreshRoleMode();
        await renderRolePermissionsEditor();
      } catch (err) {
        log('Role permissions save failed', String(err));
      }
    }

    function teamLabel(team) {
      const map = { sales: 'Sales', editorial: 'Editorial', marketing: 'Marketing', client_services: 'Client Services' };
      return map[String(team || '').toLowerCase()] || team || '-';
    }

    function seniorityLabel(level) {
      const map = { standard: 'Standard', manager: 'Manager', leadership: 'Leadership' };
      return map[String(level || '').toLowerCase()] || level || '-';
    }

    function appRoleLabel(role) {
      const map = { user: 'User', admin: 'Admin', superadmin: 'Superadmin' };
      return map[String(role || '').toLowerCase()] || role || '-';
    }

    function editableSeniorityOptions(selectedValue) {
      const current = String(selectedValue || 'standard').toLowerCase();
      const options = ['standard'];
      if (canUseControl('admin_set_user_seniority_manager', currentRole)) options.push('manager');
      if (canUseControl('admin_set_user_seniority_leadership', currentRole)) options.push('leadership');
      if (!options.includes(current)) options.push(current);
      return Array.from(new Set(options));
    }

    function editableAppRoleOptions(selectedValue) {
      const current = String(selectedValue || 'user').toLowerCase();
      const options = ['user'];
      if (canUseControl('admin_set_user_app_role_admin', currentRole)) options.push('admin');
      if (canUseControl('admin_set_user_app_role_superadmin', currentRole)) options.push('superadmin');
      if (!options.includes(current)) options.push(current);
      return Array.from(new Set(options));
    }

    function selectOptions(values, selected, labelFn) {
      return (values || []).map(v => `<option value='${v}' ${String(v) === String(selected) ? 'selected' : ''}>${labelFn(v)}</option>`).join('');
    }

    async function renderAdminUsers() {
      const card = document.getElementById('sectionAdminUsers');
      const body = document.getElementById('adminUsersBody');
      const meta = document.getElementById('adminUsersMeta');
      const createTeam = document.getElementById('adminUserTeam');
      const createSeniority = document.getElementById('adminUserSeniority');
      const createAppRole = document.getElementById('adminUserAppRole');
      const createName = document.getElementById('adminUserName');
      const createEmail = document.getElementById('adminUserEmail');
      const createButton = document.querySelector('#adminUserCreateForm button[type="submit"]');
      if (!card || !body || !meta || !createTeam || !createSeniority || !createAppRole || !createName || !createEmail || !createButton) return;
      if (!(currentRole === 'head_ops' || currentRole === 'admin')) {
        card.classList.add('hidden');
        return;
      }
      card.classList.remove('hidden');
      try {
        const payload = await api(`/api/admin/users?actor_user_id=${currentActorId}`);
        const teams = payload.teams || ['sales', 'editorial', 'marketing', 'client_services'];
        const seniorities = payload.seniorities || ['standard', 'manager', 'leadership'];
        const appRoles = payload.app_roles || ['user', 'admin', 'superadmin'];
        const canAddUser = canUseControl('admin_add_user', currentRole);
        const canEditName = canUseControl('admin_edit_user_name', currentRole);
        const canEditEmail = canUseControl('admin_edit_user_email', currentRole);
        const canSetTeam = canUseControl('admin_set_user_team', currentRole);
        const canSetMgr = canUseControl('admin_set_user_seniority_manager', currentRole);
        const canSetLead = canUseControl('admin_set_user_seniority_leadership', currentRole);
        const canRemove = canUseControl('admin_remove_user', currentRole);
        const canSetAnyAppRole = canUseControl('admin_set_user_app_role_admin', currentRole) || canUseControl('admin_set_user_app_role_superadmin', currentRole);

        createTeam.innerHTML = selectOptions(teams, 'client_services', teamLabel);
        createSeniority.innerHTML = selectOptions(editableSeniorityOptions('standard'), 'standard', seniorityLabel);
        createAppRole.innerHTML = selectOptions(editableAppRoleOptions('user'), 'user', appRoleLabel);
        createName.disabled = !canAddUser;
        createEmail.disabled = !canAddUser;
        createTeam.disabled = !canAddUser || !canSetTeam;
        createSeniority.disabled = !canAddUser || !(canSetMgr || canSetLead);
        createAppRole.disabled = !canAddUser || !canSetAnyAppRole;
        createButton.disabled = !canAddUser;

        const items = payload.items || [];
        meta.textContent = `${items.length} users`;
        body.innerHTML = `
          <div class='admin-users-wrap'>
            <table class='admin-users-table'>
              <thead><tr><th>Name</th><th>Email</th><th>Team</th><th>Seniority</th><th>App role</th><th>Actions</th></tr></thead>
              <tbody>
                ${items.map(u => `
                  <tr data-admin-user-row='${u.id}'>
                    <td><input type='text' data-admin-user-name='1' value='${escapeHtml(u.name || '')}' ${canEditName ? '' : 'disabled'} /></td>
                    <td><input type='email' data-admin-user-email='1' value='${escapeHtml(u.email || '')}' ${canEditEmail ? '' : 'disabled'} /></td>
                    <td><select data-admin-user-team='1' ${canSetTeam ? '' : 'disabled'}>${selectOptions(teams, u.primary_team || 'client_services', teamLabel)}</select></td>
                    <td><select data-admin-user-seniority='1' ${(canSetMgr || canSetLead) ? '' : 'disabled'}>${selectOptions(editableSeniorityOptions(u.seniority || 'standard'), u.seniority || 'standard', seniorityLabel)}</select></td>
                    <td><select data-admin-user-app-role='1' ${canSetAnyAppRole ? '' : 'disabled'}>${selectOptions(editableAppRoleOptions(u.app_role || 'user'), u.app_role || 'user', appRoleLabel)}</select></td>
                    <td>
                      <div style='display:flex; gap:8px; flex-wrap:wrap;'>
                        <button onclick="saveAdminUserRoles('${u.id}')">Save User</button>
                        ${canRemove ? `<button class='danger' onclick="removeAdminUser('${u.id}')">Remove</button>` : ''}
                      </div>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `;
      } catch (err) {
        body.innerHTML = `<div class='sub'>Unable to load users: ${escapeHtml(String(err))}</div>`;
      }
    }

    async function createAdminUser(event) {
      if (event) event.preventDefault();
      if (!currentActorId) return;
      try {
        if (!canUseControl('admin_add_user', currentRole)) throw new Error('You do not have permission to add users');
        const fullName = String(document.getElementById('adminUserName')?.value || '').trim();
        const email = String(document.getElementById('adminUserEmail')?.value || '').trim();
        const primaryTeam = String(document.getElementById('adminUserTeam')?.value || 'client_services').trim();
        const seniority = String(document.getElementById('adminUserSeniority')?.value || 'standard').trim();
        const appRole = String(document.getElementById('adminUserAppRole')?.value || 'user').trim();
        if (!fullName || !email) throw new Error('Name and email are required');
        await api(`/api/admin/users?actor_user_id=${currentActorId}`, {
          method: 'POST',
          body: JSON.stringify({ full_name: fullName, email, primary_team: primaryTeam, seniority, app_role: appRole }),
        });
        document.getElementById('adminUserName').value = '';
        document.getElementById('adminUserEmail').value = '';
        toast('User added', 'success');
        await Promise.all([renderAdminUsers(), loadUsersDirectory()]);
      } catch (err) {
        toast(`Unable to add user: ${String(err)}`, 'error');
      }
    }

    async function saveAdminUserRoles(userId) {
      if (!currentActorId || !userId) return;
      try {
        const row = document.querySelector(`tr[data-admin-user-row='${userId}']`);
        if (!(row instanceof HTMLElement)) throw new Error('User row not found');
        const fullName = String(row.querySelector("input[data-admin-user-name='1']")?.value || '').trim();
        const email = String(row.querySelector("input[data-admin-user-email='1']")?.value || '').trim();
        const primaryTeam = String(row.querySelector("select[data-admin-user-team='1']")?.value || 'client_services').trim();
        const seniority = String(row.querySelector("select[data-admin-user-seniority='1']")?.value || 'standard').trim();
        const appRole = String(row.querySelector("select[data-admin-user-app-role='1']")?.value || 'user').trim();
        await api(`/api/admin/users/${encodeURIComponent(userId)}/roles?actor_user_id=${currentActorId}`, {
          method: 'PUT',
          body: JSON.stringify({ full_name: fullName, email, primary_team: primaryTeam, seniority, app_role: appRole }),
        });
        toast('User profile updated', 'success');
        await Promise.all([renderAdminUsers(), loadUsersDirectory()]);
      } catch (err) {
        toast(`Unable to save user profile: ${String(err)}`, 'error');
      }
    }

    async function removeAdminUser(userId) {
      if (!currentActorId || !userId) return;
      if (!canUseControl('admin_remove_user', currentRole)) {
        toast('You do not have permission to remove users', 'error');
        return;
      }
      const confirmed = window.confirm('Remove this user? This will deactivate their access.');
      if (!confirmed) return;
      try {
        await api(`/api/admin/users/${encodeURIComponent(userId)}?actor_user_id=${currentActorId}`, { method: 'DELETE' });
        toast('User removed', 'success');
        await Promise.all([renderAdminUsers(), loadUsersDirectory()]);
      } catch (err) {
        toast(`Unable to remove user: ${String(err)}`, 'error');
      }
    }

    async function renderObjectRelationships() {
      const card = document.getElementById('sectionObjectRelationships');
      const body = document.getElementById('objectRelationshipsBody');
      const meta = document.getElementById('objectRelationshipsMeta');
      if (!card || !body || !meta) return;
      if (!(currentRole === 'head_ops' || currentRole === 'admin')) {
        card.classList.add('hidden');
        return;
      }
      card.classList.remove('hidden');
      try {
        body.innerHTML = `
          <details class='ops-accordion surface-2'>
            <summary>Parent/Child Map</summary>
            <div style='padding:8px 10px;'>
              <table>
                <thead><tr><th>Object</th><th>Parent</th><th>Children</th></tr></thead>
                <tbody>
                  <tr><td>Scope (Deal)</td><td>-</td><td>Campaigns, Product Lines, Attachments, Contacts</td></tr>
                  <tr><td>Campaign</td><td>Scope</td><td>Deliverables, Workflow Steps (campaign-owned), Milestones, Assignments, Product Modules</td></tr>
                  <tr><td>Stage (logical)</td><td>Campaign</td><td>Workflow Steps (grouped by stage)</td></tr>
                  <tr><td>Deliverable</td><td>Campaign</td><td>Workflow Steps (deliverable-owned)</td></tr>
                  <tr><td>Workflow Step</td><td>Campaign or Deliverable (exactly one)</td><td>Step Effort Allocations, Dependency links</td></tr>
                  <tr><td>Step Effort Allocation</td><td>Workflow Step</td><td>-</td></tr>
                  <tr><td>Milestone</td><td>Campaign</td><td>-</td></tr>
                  <tr><td>Campaign Assignment</td><td>Campaign</td><td>-</td></tr>
                  <tr><td>Risk / Escalation</td><td>Usually Campaign</td><td>Escalations / activity events</td></tr>
                </tbody>
              </table>
            </div>
          </details>
        `;
        meta.textContent = `Relationship map`;
      } catch (err) {
        body.innerHTML = `<div class='sub'>Unable to load object relationships: ${escapeHtml(String(err))}</div>`;
      }
    }

    async function renderDeliverables() {
      const data = await api('/api/deliverables');
      const statusFilter = getFilterValue('qDeliverables') || 'all';
      const items = data.items.filter(d => statusFilter === 'all' || String(d.status || '').toLowerCase() === statusFilter);
      const body = document.getElementById('deliverablesBody');
      const select = document.getElementById('historyDeliverableSelect');

      body.innerHTML = items.map(d => `
        <div class='queue-item'>
          ${deliverableModuleCard(d, {
            idPrefix: 'deliverables',
            actionsHtml: `<button onclick="selectDeliverableForHistory('${d.id}')">Reviews</button>`,
          })}
        </div>
      `).join('') || `<div class='sub'>No deliverables yet.</div>`;

      const options = data.items.map(d => `<option value="${d.id}">${d.id} · ${d.title}</option>`).join('');
      select.innerHTML = options || `<option value="">No deliverables</option>`;

      if (!selectedDeliverableId || !data.items.some(d => d.id === selectedDeliverableId)) {
        selectedDeliverableId = data.items.length ? data.items[0].id : null;
      }
      if (selectedDeliverableId) {
        select.value = selectedDeliverableId;
      }
      document.getElementById('deliverablesCount').textContent = `${items.length} shown / ${data.items.length} total`;

      return data.items;
    }

    function mondayOf(dateLike) {
      const d = parseDateLikeLocal(dateLike);
      if (Number.isNaN(d.getTime())) return null;
      const day = d.getDay();
      const delta = day === 0 ? -6 : 1 - day;
      d.setDate(d.getDate() + delta);
      d.setHours(0, 0, 0, 0);
      return d;
    }

    function parseDateLikeLocal(value) {
      if (value instanceof Date) return new Date(value.getTime());
      const s = String(value || '');
      const m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
      if (m) {
        return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 0, 0, 0, 0);
      }
      return new Date(value);
    }

    function isoDate(d) {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      return `${y}-${m}-${day}`;
    }

    function shiftIsoWeeks(iso, byWeeks) {
      const d = mondayOf(iso || new Date());
      d.setDate(d.getDate() + (7 * byWeeks));
      return isoDate(d);
    }

    function shiftIsoDays(iso, byDays) {
      const d = mondayOf(iso || new Date());
      d.setDate(d.getDate() + byDays);
      return isoDate(d);
    }

    function nextWorkingIsoFromIso(iso) {
      const d = parseDateLikeLocal(iso);
      if (Number.isNaN(d.getTime())) return iso;
      // Mon-Thu working week: Fri/Sat/Sun move to next Monday.
      const weekday = d.getDay();
      if (weekday === 5) d.setDate(d.getDate() + 3);
      if (weekday === 6) d.setDate(d.getDate() + 2);
      if (weekday === 0) d.setDate(d.getDate() + 1);
      return isoDate(d);
    }

    function shortWcLabel(iso) {
      const d = parseDateLikeLocal(iso);
      return `W/C ${d.toLocaleDateString(undefined, { day: '2-digit', month: 'short' })}`;
    }

    function shortDayLabel(iso) {
      const d = parseDateLikeLocal(iso);
      return d.toLocaleDateString(undefined, { weekday: 'short', day: '2-digit', month: 'short' });
    }

    function monthKeyFromIso(iso) {
      const d = parseDateLikeLocal(iso);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    }

    function monthLabelFromKey(key) {
      const [y, m] = key.split('-').map(Number);
      const d = new Date(y, (m || 1) - 1, 1);
      return d.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
    }

    function shortWeekCellLabel(iso) {
      const d = parseDateLikeLocal(iso);
      return `W/C ${d.toLocaleDateString(undefined, { day: '2-digit' })}`;
    }

    function quarterMonthGroups(columns) {
      const groups = [];
      let current = null;
      for (const col of (columns || [])) {
        const mk = monthKeyFromIso(col.key);
        if (!current || current.key !== mk) {
          current = { key: mk, label: monthLabelFromKey(mk), count: 0 };
          groups.push(current);
        }
        current.count += 1;
      }
      return groups;
    }

    function capStatusChip(cell) {
      const forecast = Number(cell.forecast_planned_hours || 0);
      const capacity = Number(cell.capacity_hours || 0);
      if (capacity <= 0 && forecast <= 0) return "<span class='tag neutral'>-</span>";
      if (forecast > capacity) return "<span class='tag risk'>Over</span>";
      if (capacity > 0 && forecast >= capacity * 0.9) return "<span class='tag review'>Near</span>";
      return "<span class='tag ok'>OK</span>";
    }

    function encodePopoverPayload(payload) {
      return encodeURIComponent(JSON.stringify(payload || {}));
    }

    function decodePopoverPayload(encoded) {
      try {
        return JSON.parse(decodeURIComponent(String(encoded || '')));
      } catch (_) {
        return null;
      }
    }

    function positionPopoverNear(pop, rect) {
      const margin = 12;
      const vw = window.innerWidth || document.documentElement.clientWidth;
      const vh = window.innerHeight || document.documentElement.clientHeight;
      const maxW = Math.max(240, vw - (margin * 2));
      const maxH = Math.max(160, vh - (margin * 2));
      pop.style.maxWidth = `${maxW}px`;
      pop.style.maxHeight = `${maxH}px`;
      pop.style.overflow = 'auto';
      const popRect = pop.getBoundingClientRect();

      let left = rect.right + 8;
      if (left + popRect.width > vw - margin) left = rect.left - popRect.width - 8;
      if (left < margin) left = margin;
      if (left + popRect.width > vw - margin) left = Math.max(margin, vw - popRect.width - margin);

      let top = rect.top;
      if (top + popRect.height > vh - margin) top = vh - margin - popRect.height;
      if (top < margin) top = margin;

      pop.style.left = `${left}px`;
      pop.style.top = `${top}px`;
    }

    function keepPopoverInViewport(pop) {
      if (!pop || pop.classList.contains('hidden')) return;
      const rect = pop.getBoundingClientRect();
      positionPopoverNear(pop, { left: rect.left, right: rect.left, top: rect.top });
    }

    function objectPanelMetaFromPayload(payload = {}) {
      const type = String(payload?.module_type || '').toLowerCase();
      const source = type === 'scope' ? payload.scope
        : type === 'campaign' ? payload.campaign
        : type === 'stage' ? payload.stage
        : type === 'deliverable' ? payload.deliverable
        : type === 'user' ? payload.user
        : payload.step;
      const title = String(source?.title || source?.name || source?.client_name || source?.id || MODULE_TYPE_LABELS[type] || 'Object');
      const userTeam = type === 'user'
        ? [source?.team, source?.editorial_subteam ? String(source.editorial_subteam).toUpperCase() : ''].filter(Boolean).join(' · ')
        : '';
      const subtitle = String(
        userTeam
        || source?.campaign_name
        || payload?.campaign?.title
        || source?.id
        || ''
      ).trim();
      const status = normalizeStatusValue(source?.status || source?.step_state || 'not_started');
      const health = String(source?.health || payload?.campaign?.health || '').toLowerCase();
      const due = source?.current_due || source?.timeframe_due || source?.sow_end_date || source?.due_date || null;
      const openPath = payload.open_deep_link || popoverOpenDeepLinkForPayload(payload) || payload.open_path || null;
      return { type, source, title, subtitle, status, health, due, openPath };
    }

    function objectPanelEditKeyFromPayload(payload = {}) {
      const meta = objectPanelMetaFromPayload(payload);
      return moduleEditKey(meta.type, String(meta.source?.id || ''));
    }

    function objectPanelIsEditing(payload = {}) {
      const key = objectPanelEditKeyFromPayload(payload);
      return key ? !!MODULE_EDIT_STATE[key] : false;
    }

    function objectPanelCanSave(meta = {}) {
      const type = String(meta.type || '').toLowerCase();
      if (type === 'scope') {
        return canUseControl('create_deal', currentRole)
          || canUseControl('ops_approve_latest_deal', currentRole)
          || canUseControl('manage_campaign_assignments', currentRole);
      }
      if (type === 'stage') {
        return canUseControl('manage_campaign_assignments', currentRole);
      }
      if (type === 'campaign') {
        return canUseControl('manage_campaign_assignments', currentRole) || canUseControl('manage_campaign_dates', currentRole);
      }
      if (type === 'deliverable') {
        return canUseControl('manage_deliverable_owner', currentRole)
          || canUseControl('manage_deliverable_dates', currentRole)
          || canUseControl('advance_deliverable', currentRole);
      }
      if (type === 'step') {
        return canUseControl('manage_step', currentRole)
          || canUseControl('manage_step_dates', currentRole)
          || canUseControl('override_step_due', currentRole)
          || canUseControl('manage_campaign_assignments', currentRole);
      }
      return false;
    }

    function objectPanelCampaignAssignmentPayload() {
      const panelBody = document.getElementById('objectPanelBody');
      const hiddenInputs = Array.from(panelBody?.querySelectorAll("input[data-campaign-assign-hidden='1']") || []);
      const byRole = campaignAssignmentsByRoleFromUsers(panelPayload?.campaign?.assigned_users || []);
      for (const input of hiddenInputs) {
        const roleKey = String(input.getAttribute('data-role-key') || '').toLowerCase();
        if (!roleKey) continue;
        byRole[roleKey] = (input.value || '').trim() || null;
      }
      return {
        actor_user_id: currentActorId,
        am_user_id: byRole.am || null,
        cm_user_id: byRole.cm || null,
        cc_user_id: byRole.cc || null,
        ccs_user_id: byRole.ccs || null,
        dn_user_id: byRole.dn || null,
        mm_user_id: byRole.mm || null,
      };
    }

    function objectPanelScopeAmPayload() {
      const panelBody = document.getElementById('objectPanelBody');
      const hiddenAm = panelBody?.querySelector("input[data-scope-assign-hidden='1'][data-role-key='am']");
      return {
        actor_user_id: currentActorId,
        am_user_id: String(hiddenAm?.value || '').trim() || null,
      };
    }

    function objectPanelScopeContentPayload(objectId) {
      const safeId = String(objectId || '').trim();
      return {
        actor_user_id: currentActorId,
        client_name: String(document.getElementById(`panelScopeClientName_${safeId}`)?.value || '').trim(),
        client_contact_name: String(document.getElementById(`panelScopeContactName_${safeId}`)?.value || '').trim(),
        client_contact_email: String(document.getElementById(`panelScopeContactEmail_${safeId}`)?.value || '').trim(),
        icp: String(document.getElementById(`panelScopeContent_icp_${safeId}`)?.value || '').trim(),
        campaign_objective: String(document.getElementById(`panelScopeContent_campaign_objective_${safeId}`)?.value || '').trim(),
        messaging_positioning: String(document.getElementById(`panelScopeContent_messaging_positioning_${safeId}`)?.value || '').trim(),
      };
    }

    function campaignAssignmentsByRoleFromUsers(users = []) {
      const byRole = {};
      for (const entry of (Array.isArray(users) ? users : [])) {
        const roleKey = String(entry?.role || '').toLowerCase().trim();
        if (!roleKey) continue;
        byRole[roleKey] = entry?.user_id ? String(entry.user_id) : null;
      }
      return byRole;
    }

    function detectCampaignAssignmentChanges(previousByRole = {}, nextPayload = {}) {
      const slotDefs = [
        { key: 'am', label: 'AM', field: 'am_user_id' },
        { key: 'cm', label: 'CM', field: 'cm_user_id' },
        { key: 'cc', label: 'Lead CC', field: 'cc_user_id' },
        { key: 'ccs', label: 'CC Support', field: 'ccs_user_id' },
        { key: 'dn', label: 'DN', field: 'dn_user_id' },
        { key: 'mm', label: 'MM', field: 'mm_user_id' },
      ];
      return slotDefs
        .map(def => {
          const oldId = previousByRole[def.key] || null;
          const newId = nextPayload[def.field] || null;
          if (oldId === newId) return null;
          const oldName = oldId ? userName(oldId) : 'Unassigned';
          const newName = newId ? userName(newId) : 'Unassigned';
          return {
            key: def.key,
            label: def.label,
            field: def.field,
            oldId,
            newId,
            oldName,
            newName,
          };
        })
        .filter(Boolean);
    }

    async function saveObjectPanelEdits() {
      if (!panelOpen || !panelPayload) return;
      if (!currentActorId) {
        toast('No active actor selected', 'error');
        return;
      }
      const meta = objectPanelMetaFromPayload(panelPayload);
      const type = String(meta.type || '').toLowerCase();
      const objectId = String(meta.source?.id || '').trim();
      if (!type || !objectId) return;
      const editKey = moduleEditKey(type, objectId);
      if (!editKey || !MODULE_EDIT_STATE[editKey]) return;
      if (!objectPanelCanSave(meta)) {
        toast('You do not have permission to save changes', 'error');
        return;
      }

      const saveBtn = document.getElementById('objectPanelSaveBtn');
      if (saveBtn instanceof HTMLButtonElement) saveBtn.disabled = true;
      try {
        if (type === 'scope') {
          const scopePayload = objectPanelScopeAmPayload();
          const scopeContentPayload = objectPanelScopeContentPayload(objectId);
          const initialAmUserId = String(panelPayload?.scope?.am_user_id || panelPayload?.scope?.am_user?.user_id || '').trim() || null;
          if (!scopePayload.am_user_id) throw new Error('AM is required');
          if (scopePayload.am_user_id !== initialAmUserId) {
            await api(`/api/scopes/${encodeURIComponent(objectId)}/am`, {
              method: 'PATCH',
              body: JSON.stringify(scopePayload),
            });
          }
          const initialClientName = String(panelPayload?.scope?.client_name || '').trim();
          const initialContactName = String(panelPayload?.scope?.client_contact_name || '').trim();
          const initialContactEmail = String(panelPayload?.scope?.client_contact_email || '').trim();
          const initialIcp = String(panelPayload?.scope?.icp || '').trim();
          const initialObjective = String(panelPayload?.scope?.campaign_objective || '').trim();
          const initialMessaging = String(panelPayload?.scope?.messaging_positioning || '').trim();
          const scopeContentChanged = (
            scopeContentPayload.client_name !== initialClientName
            || scopeContentPayload.client_contact_name !== initialContactName
            || scopeContentPayload.client_contact_email !== initialContactEmail
            || scopeContentPayload.icp !== initialIcp
            || scopeContentPayload.campaign_objective !== initialObjective
            || scopeContentPayload.messaging_positioning !== initialMessaging
          );
          if (scopeContentChanged) {
            await api(`/api/scopes/${encodeURIComponent(objectId)}/content`, {
              method: 'PATCH',
              body: JSON.stringify(scopeContentPayload),
            });
          }
        } else if (type === 'campaign' || type === 'stage') {
          const targetCampaignId = String(
            panelPayload?.campaign?.id
            || panelPayload?.campaign?.campaign_id
            || panelPayload?.stage?.campaign_id
            || ''
          ).trim();
          if (canUseControl('manage_campaign_assignments', currentRole)) {
            const panelBody = document.getElementById('objectPanelBody');
            const hasAssignmentInputs = !!panelBody?.querySelector("input[data-campaign-assign-hidden='1']");
            if (hasAssignmentInputs && targetCampaignId) {
              const assignmentPayload = objectPanelCampaignAssignmentPayload();
              const previousByRole = campaignAssignmentsByRoleFromUsers(panelPayload?.campaign?.assigned_users || []);
              const changedSlots = detectCampaignAssignmentChanges(previousByRole, assignmentPayload);
              assignmentPayload.cascade_owner_updates = false;
              if (changedSlots.length) {
                const summary = changedSlots.map(s => `${s.label}: ${s.oldName} -> ${s.newName}`).join('\\n');
                const cascadeYes = window.confirm(
                  `Assignment changes:\n${summary}\n\nAlso update deliverable/step owners for matching role records currently owned by the previous assignee?\n\nOK = Yes (cascade)\nCancel = No/Cancel`
                );
                if (cascadeYes) {
                  assignmentPayload.cascade_owner_updates = true;
                } else {
                  const saveWithoutCascade = window.confirm(
                    'Save assignment changes without updating deliverable/step owners?\\n\\n'
                    + 'OK = Save without cascade\\n'
                    + 'Cancel = Abort save'
                  );
                  if (!saveWithoutCascade) return;
                }
              }
              await api(`/api/campaigns/${encodeURIComponent(targetCampaignId)}/assignments`, {
                method: 'PATCH',
                body: JSON.stringify(assignmentPayload),
              });
            }
          }
          if (type === 'campaign' && canUseControl('manage_campaign_dates', currentRole)) {
            const startId = `panelCampaignStart_${objectId}`;
            const endId = `panelCampaignEnd_${objectId}`;
            const startRaw = (document.getElementById(startId)?.value || '').trim();
            const endRaw = (document.getElementById(endId)?.value || '').trim();
            if (startRaw || endRaw) {
              await api(`/api/campaigns/${encodeURIComponent(objectId)}/dates`, {
                method: 'PATCH',
                body: JSON.stringify({
                  actor_user_id: currentActorId,
                  planned_start_iso: startRaw ? nextWorkingIsoFromIso(startRaw) : null,
                  planned_end_iso: endRaw ? nextWorkingIsoFromIso(endRaw) : null,
                }),
              });
            }
          }
        } else if (type === 'deliverable') {
          if (canUseControl('manage_deliverable_owner', currentRole)) {
            const ownerId = `panelDeliverableOwner_${objectId}`;
            const ownerUserId = String(document.getElementById(ownerId)?.value || '').trim() || null;
            await api(`/api/deliverables/${objectId}/owner`, {
              method: 'PATCH',
              body: JSON.stringify({
                actor_user_id: currentActorId,
                owner_user_id: ownerUserId,
              }),
            });
          }
          if (canUseControl('manage_deliverable_dates', currentRole)) {
            const startId = `panelDeliverableStart_${objectId}`;
            const dueId = `panelDeliverableDue_${objectId}`;
            const startRaw = (document.getElementById(startId)?.value || '').trim();
            const dueRaw = (document.getElementById(dueId)?.value || '').trim();
            if (startRaw || dueRaw) {
              await api(`/api/deliverables/${objectId}/dates`, {
                method: 'PATCH',
                body: JSON.stringify({
                  actor_user_id: currentActorId,
                  current_start_iso: startRaw ? nextWorkingIsoFromIso(startRaw) : null,
                  current_due_iso: dueRaw ? nextWorkingIsoFromIso(dueRaw) : null,
                  reason_code: 'schedule_adjustment',
                }),
              });
            }
          }
          if (canUseControl('advance_deliverable', currentRole)) {
            const panelBody = document.getElementById('objectPanelBody');
            const statusDropdown = panelBody?.querySelector(".pill-dropdown[data-object-type='deliverable']");
            const hiddenDelivery = panelBody?.querySelector("input[data-delivery-status='1']");
            const currentRaw = String(hiddenDelivery?.value || statusDropdown?.getAttribute('data-current-raw') || '').toLowerCase().trim();
            const initialRaw = String(panelPayload?.deliverable?.delivery_status || '').toLowerCase().trim();
            if (currentRaw && currentRaw !== initialRaw) {
              await api(`/api/deliverables/${objectId}/transition`, {
                method: 'POST',
                body: JSON.stringify({
                  actor_user_id: currentActorId,
                  to_status: currentRaw,
                  comment: 'Status updated from side panel edit mode',
                }),
              });
            }
          }
        } else if (type === 'step') {
          const ids = statusContextIds(objectId, 'panel');
          const reasonEl = ids.reasonId ? document.getElementById(ids.reasonId) : null;
          const dueEl = ids.dueId ? document.getElementById(ids.dueId) : null;
          const startEl = document.getElementById(`panelStepStart_${objectId}`);
          const canManageStepDates = canUseControl('manage_step_dates', currentRole) || canUseControl('override_step_due', currentRole);
          const dueRaw = (dueEl?.value || '').trim();
          const startRaw = (startEl?.value || '').trim();
          const payload = { actor_user_id: currentActorId };
          if (canUseControl('manage_step', currentRole)) {
            const status = normalizeStatusValue(document.getElementById(ids.hiddenStatusId)?.value || 'not_started');
            const ownerId = ownerFieldValue(ids.ownerId);
            payload.status = status;
            payload.next_owner_user_id = ownerId;
            payload.waiting_on_user_id = null;
            payload.blocker_reason = reasonEl?.value || null;
          }
          if (canManageStepDates && (startRaw || dueRaw)) {
            payload.current_start_iso = startRaw ? nextWorkingIsoFromIso(startRaw) : null;
            payload.current_due_iso = dueRaw ? nextWorkingIsoFromIso(dueRaw) : null;
          }
          if (Object.keys(payload).length > 1) {
            await api(`/api/workflow-steps/${objectId}/manage`, {
              method: 'PATCH',
              body: JSON.stringify(payload),
            });
          }
          if (canUseControl('manage_campaign_assignments', currentRole) || canUseControl('manage_step', currentRole)) {
            const targetCampaignId = String(
              panelPayload?.campaign?.id
              || panelPayload?.campaign?.campaign_id
              || panelPayload?.step?.campaign_id
              || ''
            ).trim();
            const panelBody = document.getElementById('objectPanelBody');
            const hasAssignmentInputs = !!panelBody?.querySelector("input[data-campaign-assign-hidden='1']");
            if (targetCampaignId && hasAssignmentInputs) {
              const assignmentPayload = objectPanelCampaignAssignmentPayload();
              const previousByRole = campaignAssignmentsByRoleFromUsers(panelPayload?.campaign?.assigned_users || []);
              const changedSlots = detectCampaignAssignmentChanges(previousByRole, assignmentPayload);
              assignmentPayload.cascade_owner_updates = false;
              if (changedSlots.length) {
                const summary = changedSlots.map(s => `${s.label}: ${s.oldName} -> ${s.newName}`).join('\\n');
                const cascadeYes = window.confirm(
                  `Assignment changes:\n${summary}\n\nAlso update deliverable/step owners for matching role records currently owned by the previous assignee?\n\nOK = Yes (cascade)\nCancel = No/Cancel`
                );
                if (cascadeYes) {
                  assignmentPayload.cascade_owner_updates = true;
                } else {
                  const saveWithoutCascade = window.confirm(
                    'Save assignment changes without updating deliverable/step owners?\\n\\n'
                    + 'OK = Save without cascade\\n'
                    + 'Cancel = Abort save'
                  );
                  if (!saveWithoutCascade) return;
                }
              }
              await api(`/api/campaigns/${encodeURIComponent(targetCampaignId)}/assignments`, {
                method: 'PATCH',
                body: JSON.stringify(assignmentPayload),
              });
            }
          }
        }

        if (editKey) MODULE_EDIT_STATE[editKey] = false;
        const campaignId = String(
          panelPayload?.campaign?.id
          || panelPayload?.stage?.campaign_id
          || panelPayload?.deliverable?.campaign_id
          || panelPayload?.step?.campaign_id
          || ''
        ).trim();
        const refreshed = await fetchObjectPanelPayload(type, objectId, campaignId);
        if (refreshed) openObjectPanelByPayload(refreshed);
        toast('Changes saved', 'success');
      } catch (err) {
        toast(`Unable to save panel changes: ${String(err)}`, 'error');
        log('Object panel save failed', String(err));
      } finally {
        if (saveBtn instanceof HTMLButtonElement) saveBtn.disabled = false;
      }
    }

    function objectPanelHeaderHtml(payload = {}) {
      const meta = objectPanelMetaFromPayload(payload);
      const canMenuEdit = canEditFromModuleMenu(meta.type);
      const editing = canMenuEdit && isModuleEditing(meta.type, String(meta.source?.id || ''));
      const canDeleteCampaign = meta.type === 'campaign' && canUseControl('delete_campaign', currentRole);
      const canDeleteDeliverable = meta.type === 'deliverable' && canUseControl('delete_deliverable', currentRole);
      const menuActions = [
        `<button type='button' class='module-options-item' data-module-menu-action='open' data-module-type='${meta.type}' data-object-id='${String(meta.source?.id || '')}' data-campaign-id='${String(payload?.campaign?.id || meta.source?.campaign_id || '')}'>Open</button>`,
        canMenuEdit
          ? `<button type='button' class='module-options-item' data-module-menu-action='edit' data-module-type='${meta.type}' data-object-id='${String(meta.source?.id || '')}' data-campaign-id='${String(payload?.campaign?.id || meta.source?.campaign_id || '')}'>${editing ? 'Done Editing' : 'Edit'}</button>`
          : '',
        canDeleteCampaign
          ? `<button type='button' class='module-options-item danger' data-module-menu-action='delete' data-module-type='campaign' data-object-id='${String(meta.source?.id || '')}'>Delete Campaign</button>`
          : '',
        canDeleteDeliverable
          ? `<button type='button' class='module-options-item danger' data-module-menu-action='delete' data-module-type='deliverable' data-object-id='${String(meta.source?.id || '')}'>Delete Deliverable</button>`
          : '',
      ].filter(Boolean).join('');
      const menu = `
        <div class='module-options' data-module-options='1' data-options-wrap='1'>
          ${moduleOptionsButton()}
          <div class='module-options-menu'>
            ${menuActions || "<button type='button' class='module-options-item' disabled>No actions</button>"}
          </div>
        </div>
      `;
      return `
        <div class='object-panel-title-row'>
          <div class='object-panel-title-left'>
            <span class='module-icon'>${moduleIcon(meta.type)}</span>
            <div class='object-panel-title-text'>
              <div class='object-panel-title'>${escapeHtml(meta.title)}</div>
              ${meta.subtitle ? `<div class='object-panel-subtitle'>${escapeHtml(meta.subtitle)}</div>` : ''}
            </div>
          </div>
          <div class='module-head-controls'>${menu}<button type='button' class='ghost module-option-btn module-close-btn' onclick='closeObjectPanel()' aria-label='Close panel' title='Close panel'>X</button></div>
        </div>
      `;
    }

    function objectPanelFooterHtml(payload = {}) {
      const meta = objectPanelMetaFromPayload(payload);
      const dueText = meta.due ? `Due ${niceDate(meta.due)}` : '';
      const editing = objectPanelIsEditing(payload);
      const canSave = editing && objectPanelCanSave(meta);
      const saveBtn = canSave ? `<button id='objectPanelSaveBtn' class='primary' onclick='saveObjectPanelEdits()'>Save</button>` : '';
      const campaignId = String(payload?.campaign?.id || payload?.campaign?.campaign_id || '').trim();
      const showCampaignCascade = meta.type === 'campaign' && !!campaignId && canUseControl('manage_campaign_status', currentRole);
      const campaignButtons = showCampaignCascade
        ? `<button onclick="cascadeCampaignDescendantStatus('${campaignId.replace(/'/g, '&#39;')}')">Cascade Descendant Status</button>`
        : '';
      const scopeStatus = String(payload?.scope?.status || '').toLowerCase();
      const scopeId = String(payload?.scope?.id || '').trim();
      const safeScopeId = scopeId.replace(/'/g, '&#39;');
      const showScopeApprove = meta.type === 'scope'
        && !!scopeId
        && canApproveScopes()
        && ['submitted', 'readiness_failed', 'ops_approved', 'draft'].includes(scopeStatus);
      const showScopeGenerate = meta.type === 'scope'
        && !!scopeId
        && canGenerateScopeCampaigns()
        && scopeStatus === 'readiness_passed';
      const scopeButtons = (showScopeApprove || showScopeGenerate)
        ? `${showScopeApprove ? `<button onclick="approveScope('${safeScopeId}')">Approve</button>` : ''}${showScopeGenerate ? `<button class='primary' onclick="generateCampaignsForScope('${safeScopeId}')">Generate</button>` : ''}`
        : '';
      const openBtn = (meta.type !== 'scope' && meta.openPath)
        ? `<button class='primary' onclick='window.location.href="${String(meta.openPath).replace(/"/g, '&quot;')}"'>Open</button>`
        : '';
      return `
        <div class='object-panel-footer-left'>
          ${statusChip(meta.status)}
          ${meta.health ? healthChip(meta.health) : ''}
          ${dueText ? `<span class='due-text'>${dueText}</span>` : ''}
        </div>
        <div class='object-panel-footer-right'>
          ${saveBtn}
          ${campaignButtons}
          ${scopeButtons}
          ${openBtn}
        </div>
      `;
    }

    function closeObjectPanel() {
      panelOpen = false;
      panelObjectType = '';
      panelObjectId = '';
      panelPayload = null;
      const panel = document.getElementById('objectPanel');
      const backdrop = document.getElementById('objectPanelBackdrop');
      const body = document.getElementById('objectPanelBody');
      const header = document.getElementById('objectPanelHeader');
      const footer = document.getElementById('objectPanelFooter');
      if (panel) {
        panel.classList.remove('open');
        panel.classList.add('hidden');
      }
      if (backdrop) {
        backdrop.classList.remove('open');
        backdrop.classList.add('hidden');
      }
      if (body) body.innerHTML = '';
      if (header) header.innerHTML = '';
      if (header) header.removeAttribute('data-module');
      if (footer) footer.innerHTML = '';
    }

    function closeItemPopover() {
      closeObjectPanel();
    }

    function syncObjectPanelHeaderIconSize(headerEl) {
      const header = headerEl instanceof HTMLElement ? headerEl : document.getElementById('objectPanelHeader');
      if (!header) return;
      const icon = header.querySelector('.object-panel-title-left .module-icon');
      const textWrap = header.querySelector('.object-panel-title-text');
      if (!(icon instanceof HTMLElement) || !(textWrap instanceof HTMLElement)) return;
      const textHeight = Math.max(0, Math.round(textWrap.getBoundingClientRect().height));
      if (!textHeight) return;
      icon.style.width = `${textHeight}px`;
      icon.style.height = `${textHeight}px`;
    }

    function objectPanelPrimaryObjectId(payload = {}) {
      const type = String(payload?.module_type || '').toLowerCase().trim();
      if (type === 'scope') return String(payload?.scope?.id || '').trim();
      if (type === 'campaign') return String(payload?.campaign?.id || payload?.campaign?.campaign_id || '').trim();
      if (type === 'stage') return String(payload?.stage?.id || payload?.stage?.display_id || '').trim();
      if (type === 'deliverable') return String(payload?.deliverable?.id || payload?.deliverable?.display_id || '').trim();
      if (type === 'step') return String(payload?.step?.id || payload?.step?.display_id || '').trim();
      if (type === 'user') return String(payload?.user?.id || '').trim();
      return String(
        payload?.scope?.id
        || payload?.campaign?.id
        || payload?.campaign?.campaign_id
        || payload?.stage?.id
        || payload?.stage?.display_id
        || payload?.deliverable?.id
        || payload?.deliverable?.display_id
        || payload?.step?.id
        || payload?.step?.display_id
        || payload?.user?.id
        || ''
      ).trim();
    }

    function extractPanelModuleBodyHtml(moduleHtml = '') {
      const html = String(moduleHtml || '').trim();
      if (!html) return html;
      const template = document.createElement('template');
      template.innerHTML = html;
      const fields = template.content.querySelector('.module-popover .module-fields')
        || template.content.querySelector('.module-card .module-fields');
      return fields ? fields.outerHTML : html;
    }

    function panelBodyModulesHtml(baseHtml = '', teamModulesHtml = '', childrenModulesHtml = '') {
      const bodyHtml = String(baseHtml || '').trim();
      const teamModules = String(teamModulesHtml || '').trim();
      const childModules = String(childrenModulesHtml || '').trim();
      if (!bodyHtml && !teamModules && !childModules) return '';
      return `${bodyHtml}${teamModules}${childModules}`;
    }

    function openObjectPanelByPayload(payload) {
      if (!payload) return;
      const panel = document.getElementById('objectPanel');
      const backdrop = document.getElementById('objectPanelBackdrop');
      const body = document.getElementById('objectPanelBody');
      const header = document.getElementById('objectPanelHeader');
      const footer = document.getElementById('objectPanelFooter');
      if (!panel || !body || !header || !footer) return;
      const details = Array.isArray(payload.details) ? payload.details : [];
      let moduleHtml = '';
      if (payload.module_type === 'step' && payload.step) {
        const stepId = String(payload.step.id || '');
        moduleHtml = stepModuleCard(
          {
            step: payload.step,
            stage: payload.stage || null,
            deliverable: payload.deliverable || { title: '-' },
            campaign: payload.campaign || { id: '-', title: '-' },
            derived: { is_overdue: !!(payload.step.current_due && payload.step.current_due < isoDate(new Date())) },
          },
          {
            popover: true,
            panel: true,
            dropdownContext: 'panel',
            idPrefix: `panelStep_${stepId || 'step'}`,
            startId: `panelStepStart_${stepId || 'step'}`,
            dueId: `panelStepDue_${stepId || 'step'}`,
            statusId: `panelStepAction_${stepId || 'step'}`,
            ownerId: `panelStepOwner_${stepId || 'step'}`,
            reasonId: `panelStepReason_${stepId || 'step'}`,
            openPath: payload.open_deep_link || popoverOpenDeepLinkForPayload(payload) || payload.open_path || null,
            openLabel: payload.open_label || 'Open',
          }
        );
      } else if (payload.module_type === 'deliverable' && payload.deliverable) {
        const deliverableId = String(payload.deliverable.id || '');
        moduleHtml = deliverableModuleCard(payload.deliverable, {
          popover: true,
          panel: true,
          dropdownContext: 'panel',
          idPrefix: `panelDeliverable_${deliverableId || 'deliverable'}`,
          startId: `panelDeliverableStart_${deliverableId || 'deliverable'}`,
          dueId: `panelDeliverableDue_${deliverableId || 'deliverable'}`,
          ownerId: `panelDeliverableOwner_${deliverableId || 'deliverable'}`,
          openPath: payload.open_deep_link || popoverOpenDeepLinkForPayload(payload) || payload.open_path || null,
          openLabel: payload.open_label || 'Open',
        });
      } else if (payload.module_type === 'campaign' && payload.campaign) {
        const campaignId = String(payload.campaign.id || payload.campaign.campaign_id || '');
        moduleHtml = campaignModuleCard({
          ...payload.campaign,
          deliverables: [],
          work_steps: [],
          deliverables_summary: payload.campaign.deliverables_summary || { total: 0, not_started: 0, in_progress: 0, done: 0 },
          work_summary: payload.campaign.work_summary || { total: 0, not_started: 0, in_progress: 0, done: 0 },
        }, {
          popover: true,
          panel: true,
          dropdownContext: 'panel',
          idPrefix: `panelCampaign_${campaignId || 'campaign'}`,
          startId: `panelCampaignStart_${campaignId || 'campaign'}`,
          endId: `panelCampaignEnd_${campaignId || 'campaign'}`,
          openPath: payload.open_deep_link || popoverOpenDeepLinkForPayload(payload) || payload.open_path || null,
          openLabel: payload.open_label || 'Open',
        });
      } else if (payload.module_type === 'scope' && payload.scope) {
        moduleHtml = scopeModuleCard(payload.scope, {
          popover: true,
          panel: true,
          openPath: payload.open_deep_link || popoverOpenDeepLinkForPayload(payload) || payload.open_path || null,
          openLabel: payload.open_label || 'Open',
        });
      } else if (payload.module_type === 'stage' && payload.stage) {
        moduleHtml = stageModuleCard(payload.stage, {
          popover: true,
          panel: true,
          openPath: payload.open_deep_link || popoverOpenDeepLinkForPayload(payload) || payload.open_path || null,
          openLabel: payload.open_label || 'Open',
        });
      } else if (payload.module_type === 'user' && payload.user) {
        const u = payload.user || {};
        const capRows = Array.isArray(u?.capacity?.rows) ? u.capacity.rows : [];
        const campaigns = Array.isArray(u?.campaigns_participated) ? u.campaigns_participated : [];
        moduleHtml = [
          userPanelDetailsModuleHtml(u),
          userPanelCampaignsModuleHtml(campaigns),
          userPanelCapacityModuleHtml(capRows),
        ].join('');
      }
      panelPayload = payload;
      panelOpen = true;
      panelObjectType = String(payload.module_type || '').toLowerCase();
      panelObjectId = objectPanelPrimaryObjectId(payload);
      header.innerHTML = objectPanelHeaderHtml(payload);
      if (panelObjectType) {
        header.setAttribute('data-module', panelObjectType);
      } else {
        header.removeAttribute('data-module');
      }
      syncObjectPanelHeaderIconSize(header);
      requestAnimationFrame(() => syncObjectPanelHeaderIconSize(header));
      footer.innerHTML = objectPanelFooterHtml(payload);
      const panelType = String(payload?.module_type || '').toLowerCase();
      const bodyBaseHtml = (panelType === 'user')
        ? String(moduleHtml || '').trim()
        : (extractPanelModuleBodyHtml(moduleHtml)
            || `<div class='cap-popover-list'>${details.map(d => `<div class='cap-pop-item'>${d}</div>`).join('') || "<div class='sub'>No details available.</div>"}</div>`);
      const progressHtml = objectPanelProgressHtml(payload);
      const teamHtml = objectPanelTeamHtml(payload);
      const scopeContentHtml = objectPanelScopeContentHtml(payload);
      const childrenHtml = objectPanelChildrenHtml(payload);
      body.innerHTML = panelBodyModulesHtml(bodyBaseHtml, `${progressHtml}${childrenHtml}${teamHtml}${scopeContentHtml}`, '');
      panel.classList.add('open');
      panel.classList.remove('hidden');
      const isMobile = (window.innerWidth || 0) <= 980;
      if (backdrop) {
        backdrop.classList.toggle('open', isMobile);
        backdrop.classList.toggle('hidden', !isMobile);
      }
      requestAnimationFrame(() => applyModuleLayoutRules(panel));
    }

    function objectPanelIdentifiersFromPayload(payload = {}) {
      const type = String(payload?.module_type || '').toLowerCase().trim();
      const objectId = objectPanelPrimaryObjectId(payload);
      const campaignId = String(
        payload?.campaign?.id
        || payload?.stage?.campaign_id
        || payload?.deliverable?.campaign_id
        || payload?.step?.campaign_id
        || ''
      ).trim();
      return { type, objectId, campaignId };
    }

    async function openObjectPanelByDecodedPayload(payload) {
      if (!payload) return;
      const { type, objectId, campaignId } = objectPanelIdentifiersFromPayload(payload);
      if (type && objectId) {
        try {
          const fetched = await fetchObjectPanelPayload(type, objectId, campaignId);
          if (fetched) {
            openObjectPanelByPayload(fetched);
            return;
          }
        } catch (err) {
          log('Object panel canonical fetch failed', String(err));
        }
      }
      openObjectPanelByPayload(payload);
    }

    async function openObjectPanelByEncoded(payloadEncoded) {
      const payload = decodePopoverPayload(payloadEncoded);
      if (!payload) return;
      await openObjectPanelByDecodedPayload(payload);
    }

    async function openItemPopoverByPayload(buttonEl, payloadEncoded) {
      const payload = decodePopoverPayload(payloadEncoded);
      if (!payload) return;
      await openObjectPanelByDecodedPayload(payload);
    }

    async function openObjectPanelChild(moduleType, objectId, campaignId = '') {
      const type = String(moduleType || '').toLowerCase().trim();
      const id = String(objectId || '').trim();
      const cid = String(campaignId || '').trim();
      if (!type || !id) return;
      const payload = await fetchObjectPanelPayload(type, id, cid);
      if (!payload) {
        toast('Unable to open child object', 'error');
        return;
      }
      openObjectPanelByPayload(payload);
    }

    function capacityCellKey(userId, weekStart) {
      return `${userId}:${weekStart}`;
    }

    function indexItemsForUser(userId) {
      const indexed = {};
      for (const column of (capacityColumns || [])) {
        const cell = (capacityDisplayCells || {})[capacityCellKey(userId, column.key)];
        for (const item of (cell?.items || [])) {
          if (!item?.step_id) continue;
          indexed[item.step_id] = item;
        }
      }
      return Object.values(indexed);
    }

    function itemsForPillLane(userId) {
      const baseItems = indexItemsForUser(userId);
      if (capacityView !== 'quarter') return baseItems;
      const grouped = {};
      for (const item of baseItems) {
        const campaignId = item?.campaign_id || null;
        if (!campaignId) {
          grouped[`step:${item.step_id}`] = item;
          continue;
        }
        const key = `campaign:${campaignId}`;
        if (!grouped[key]) {
          grouped[key] = {
            ...item,
            step_id: `CAMP:${campaignId}`,
            step_name: item.campaign_title || campaignId,
            step_kind: 'task',
            planned_hours: 0,
            grouped_steps_count: 0,
          };
        }
        const g = grouped[key];
        g.planned_hours = Number(g.planned_hours || 0) + Number(item.planned_hours || 0);
        g.grouped_steps_count = Number(g.grouped_steps_count || 0) + 1;

        const gStart = g.start ? parseDateLikeLocal(g.start) : null;
        const gEnd = g.end ? parseDateLikeLocal(g.end) : null;
        const iStart = item.start ? parseDateLikeLocal(item.start) : null;
        const iEnd = item.end ? parseDateLikeLocal(item.end) : null;
        const iDue = item.due ? parseDateLikeLocal(item.due) : null;

        if (iStart && (!gStart || iStart < gStart)) g.start = isoDate(iStart);
        const candidateEnd = iEnd || iDue;
        if (candidateEnd && (!gEnd || candidateEnd > gEnd)) {
          g.end = isoDate(candidateEnd);
          g.due = isoDate(candidateEnd);
        }
      }
      return Object.values(grouped);
    }

    function bucketKeyForDate(iso) {
      if (!iso) return null;
      if (capacityGranularity === 'day') return iso;
      if (capacityView === 'quarter') return monthKeyFromIso(iso);
      const monday = mondayOf(`${iso}T00:00:00`);
      return monday ? isoDate(monday) : null;
    }

    function capacityHoursPerColumn() {
      return capacityGranularity === 'day' ? 8 : 32;
    }

    function capacitySubunitsPerColumn() {
      if (capacityGranularity === 'day') return 8; // 8 hours per day
      if (capacityView === 'month') return 4; // 4 working days per week
      return 40; // quarter: 5 week microsplits × 8 hour units
    }

    function capacityTimeColWidthPx() {
      const raw = getComputedStyle(document.documentElement).getPropertyValue('--capacity-time-col-width').trim();
      const parsed = Number.parseFloat(raw.replace('px', ''));
      return Number.isFinite(parsed) && parsed > 0 ? parsed : 220;
    }

    function isWorkingDayLocal(d) {
      const wd = d.getDay();
      return wd >= 1 && wd <= 4; // Mon-Thu
    }

    function nextWorkingDayLocal(d) {
      const c = new Date(d.getTime());
      c.setHours(0, 0, 0, 0);
      while (!isWorkingDayLocal(c)) c.setDate(c.getDate() + 1);
      return c;
    }

    function addDaysLocal(d, days) {
      const c = new Date(d.getTime());
      c.setDate(c.getDate() + days);
      return c;
    }

    function pickCapacityPillTone(item) {
      const kind = String(item?.step_kind || '').toLowerCase();
      if (kind === 'call') return 'tone-cobalt';
      if (kind === 'approval') return 'tone-amber';
      return 'tone-sage';
    }

    function capacityItemModulePayload(i) {
      const ownerName = userName(i?.step_owner_user_id);
      const ownerInitials = i?.step_owner_user_id ? initialsFromName(ownerName || '') : '--';
      const groupedCampaignRow = String(i?.step_id || '').startsWith('CAMP:');
      if (groupedCampaignRow) {
        const campaignPayload = {
          title: i?.campaign_title || i?.campaign_id || 'Campaign',
          module_type: 'campaign',
          campaign: {
            id: i?.campaign_id || '-',
            title: i?.campaign_title || '-',
            status: i?.campaign_status || 'not_started',
            health: i?.campaign_health || 'not_started',
            timeframe_start: i?.start || null,
            timeframe_due: i?.due || i?.end || null,
            assigned_users: [],
            deliverables_summary: { total: 0, not_started: 0, in_progress: 0, done: 0 },
            work_summary: {
              total: Number(i?.grouped_steps_count || 0),
              not_started: 0,
              in_progress: Number(i?.grouped_steps_count || 0),
              done: 0,
            },
          },
          details: [
            `Campaign: ${i?.campaign_id || '-'}`,
            `Grouped steps: ${i?.grouped_steps_count || 0}`,
            `Start: ${i?.start || '-'}`,
            `Due: ${i?.due || i?.end || '-'}`,
          ],
          target_type: 'campaign',
          target_id: i?.campaign_id || '',
          campaign_id: i?.campaign_id || '',
          open_path: i?.campaign_id ? '/campaigns' : '/capacity',
          open_label: i?.campaign_id ? 'Open Campaigns' : 'Open Capacity',
        };
        campaignPayload.open_deep_link = popoverOpenDeepLinkForPayload(campaignPayload);
        return campaignPayload;
      }
      const payload = {
        title: i?.step_name || 'Capacity item',
        module_type: 'step',
        campaign: {
          id: i?.campaign_id || '-',
          title: i?.campaign_title || '-',
        },
        deliverable: {
          id: i?.deliverable_id || null,
          title: i?.deliverable_title || '-',
          status: i?.deliverable_status || 'not_started',
        },
        step: {
          id: i?.step_id || '',
          name: i?.step_name || 'Step',
          step_kind: i?.step_kind || 'task',
          status: i?.step_status || 'not_started',
          health: i?.step_health || 'not_started',
          current_start: i?.start || null,
          current_due: i?.due || i?.end || null,
          next_owner_user_id: i?.step_owner_user_id || null,
          owner_initials: ownerInitials,
          participant_initials: [],
          blocker_reason: i?.waiting_on_type ? `Waiting on ${i.waiting_on_type}` : null,
        },
        details: [
          `Campaign: ${i?.campaign_id || '-'}`,
          ...(i?.grouped_steps_count ? [`Grouped steps: ${i.grouped_steps_count}`] : []),
          `Parent: ${i?.parent_type || '-'}`,
          `Deliverable: ${i?.deliverable_title || '-'}`,
          `Start: ${i?.start || '-'}`,
          `Due: ${i?.due || '-'}`,
          `Waiting: ${i?.waiting_on_type || '-'}`,
        ],
        open_path: i?.campaign_id ? '/campaigns' : '/capacity',
        open_label: i?.campaign_id ? 'Open Campaigns' : 'Open Capacity',
      };
      payload.open_deep_link = popoverOpenDeepLinkForPayload(payload);
      payload.target_type = 'step';
      payload.target_id = i?.step_id || '';
      payload.campaign_id = i?.campaign_id || '';
      return payload;
    }

    function pillRenderMode(stepName, spanUnits) {
      const unitPx = capacityTimeColWidthPx() / capacitySubunitsPerColumn();
      const widthPx = Math.max(1, spanUnits) * unitPx;
      if (widthPx < 16) return 'dot';
      const estimatedLabelPx = Math.max(36, String(stepName || '').length * 6.6);
      if (widthPx < estimatedLabelPx) return 'side';
      return 'inside';
    }

    function nextWeekBucketDate(d) {
      const m = mondayOf(d);
      const c = new Date(m.getTime());
      c.setDate(c.getDate() + 7);
      return c;
    }

    function startBucketDate(firstDate) {
      if (capacityGranularity === 'day') return nextWorkingDayLocal(firstDate);
      return mondayOf(firstDate);
    }

    function nextBucketDate(current) {
      if (capacityGranularity === 'day') return nextWorkingDayLocal(addDaysLocal(current, 1));
      return nextWeekBucketDate(current);
    }

    function buildOccupancySpans(items, columnIndexByKey, subunitsPerCol, hoursPerCol) {
      const spans = [];
      for (const item of (items || [])) {
        const firstDateRaw = item?.start || item?.due;
        const firstDate = parseDateLikeLocal(firstDateRaw);
        if (!firstDate || Number.isNaN(firstDate.getTime())) continue;
        let cursor = startBucketDate(firstDate);
        let remaining = Number(item?.planned_hours || 0);
        if (!(remaining > 0)) continue;

        let firstUnit = null;
        let totalUnits = 0;
        let guard = 0;
        while (remaining > 0 && guard < 400) {
          guard += 1;
          const bucketKey = bucketKeyForDate(isoDate(cursor));
          const alloc = Math.min(remaining, hoursPerCol);
          const idx = bucketKey ? columnIndexByKey[bucketKey] : null;
          if (idx !== null && idx !== undefined) {
            const units = Math.max(1, Math.ceil((alloc / hoursPerCol) * subunitsPerCol));
            if (firstUnit === null) {
              firstUnit = (idx * subunitsPerCol) + 1;
            }
            totalUnits += units;
          }
          remaining -= alloc;
          cursor = nextBucketDate(cursor);
        }
        if (firstUnit === null || totalUnits <= 0) continue;
        spans.push({
          item,
          startUnit: firstUnit,
          endUnit: firstUnit + totalUnits - 1,
          units: totalUnits,
        });
      }

      spans.sort((a, b) => (a.startUnit - b.startUnit) || (a.endUnit - b.endUnit) || String(a.item.step_name || '').localeCompare(String(b.item.step_name || '')));
      const lanes = [];
      const laneEnds = [];
      for (const span of spans) {
        let lane = 0;
        while (lane < laneEnds.length && span.startUnit <= laneEnds[lane]) lane += 1;
        if (lane === laneEnds.length) {
          laneEnds.push(-1);
          lanes.push([]);
        }
        lanes[lane].push(span);
        laneEnds[lane] = span.endUnit;
      }
      return lanes;
    }

    function buildQuarterOccupancySpans(items, columnIndexByKey) {
      const spans = [];
      for (const item of (items || [])) {
        const firstDateRaw = item?.start || item?.due;
        const firstDate = parseDateLikeLocal(firstDateRaw);
        if (!firstDate || Number.isNaN(firstDate.getTime())) continue;
        let cursor = mondayOf(firstDate);
        let remaining = Number(item?.planned_hours || 0);
        if (!(remaining > 0)) continue;

        let firstUnit = null;
        let totalUnits = 0;
        let guard = 0;
        while (remaining > 0 && guard < 400) {
          guard += 1;
          const weekKey = isoDate(cursor);
          const slot = capacityQuarterWeekSlots[weekKey];
          if (slot) {
            const monthIdx = columnIndexByKey[slot.monthKey];
            if (monthIdx !== null && monthIdx !== undefined) {
              const alloc = Math.min(remaining, 32);
              const units = Math.max(1, Math.ceil((alloc / 32) * 8)); // 8 hour-subunits per week microsplit
              const monthUnitBase = (monthIdx * 40) + (slot.weekSlot * 8);
              const startUnit = monthUnitBase + 1;
              if (firstUnit === null) firstUnit = startUnit;
              totalUnits += units;
              remaining -= alloc;
            } else {
              remaining -= Math.min(remaining, 32);
            }
          } else {
            remaining -= Math.min(remaining, 32);
          }
          cursor = nextWeekBucketDate(cursor);
        }

        if (firstUnit === null || totalUnits <= 0) continue;
        spans.push({
          item,
          startUnit: firstUnit,
          endUnit: firstUnit + totalUnits - 1,
          units: totalUnits,
        });
      }

      spans.sort((a, b) => (a.startUnit - b.startUnit) || (a.endUnit - b.endUnit) || String(a.item.step_name || '').localeCompare(String(b.item.step_name || '')));
      const lanes = [];
      const laneEnds = [];
      for (const span of spans) {
        let lane = 0;
        while (lane < laneEnds.length && span.startUnit <= laneEnds[lane]) lane += 1;
        if (lane === laneEnds.length) {
          laneEnds.push(-1);
          lanes.push([]);
        }
        lanes[lane].push(span);
        laneEnds[lane] = span.endUnit;
      }
      return lanes;
    }

    function capacityCellClass(cell) {
      const forecast = Number(cell.forecast_planned_hours || 0);
      const capacity = Number(cell.capacity_hours || 0);
      if (capacity > 0 && forecast > capacity) return 'capacity-cell-over';
      if (capacity > 0 && forecast >= capacity * 0.9) return 'capacity-cell-near';
      if (capacity > 0 && forecast > 0) return 'capacity-cell-ok';
      return '';
    }

    function renderCapacityPillLane(user) {
      if (!capacityShowItems || !capacityColumns.length) return '';
      const items = itemsForPillLane(user.user_id);
      if (!items.length) return '';
      const columnIndexByKey = {};
      capacityColumns.forEach((col, idx) => { columnIndexByKey[col.key] = idx; });
      const subunitsPerCol = capacitySubunitsPerColumn();
      const hoursPerCol = capacityHoursPerColumn();
      const totalSubunits = capacityColumns.length * subunitsPerCol;
      const lanes = capacityView === 'quarter'
        ? buildQuarterOccupancySpans(items, columnIndexByKey)
        : buildOccupancySpans(items, columnIndexByKey, subunitsPerCol, hoursPerCol);
      if (!lanes.length) return '';

      const tracks = lanes.map(lane => {
        const pills = lane.map(span => {
          const i = span.item;
          const ownerUserId = i.step_owner_user_id || null;
          const isOwner = !ownerUserId || ownerUserId === user.user_id;
          const mode = pillRenderMode(i.step_name, span.units);
          const cls = `cap-pill ${pickCapacityPillTone(i)} ${isOwner ? '' : 'non-owner'} ${mode === 'side' ? 'compact' : ''} ${mode === 'dot' ? 'dot' : ''}`.trim();
          const groupMeta = i.grouped_steps_count ? ` · ${i.grouped_steps_count} steps` : '';
          const tooltip = `${i.step_name}${groupMeta} · ${i.campaign_id || '-'} · ${i.start || '-'} to ${i.end || '-'}`;
          const payload = encodePopoverPayload(capacityItemModulePayload(i));
          const sideLabel = mode === 'side' ? `<span class='cap-pill-side'>${i.step_name}</span>` : '';
          const buttonLabel = mode === 'dot' ? '&bull;' : (mode === 'side' ? '' : i.step_name);
          const wrapClass = `cap-pill-wrap ${mode === 'dot' ? 'dot-wrap' : ''}`.trim();
          return `
            <div class='${wrapClass}' style='grid-column:${span.startUnit} / ${span.endUnit + 1};' title='${tooltip}'>
              <button class='${cls}' onclick='openItemPopoverByPayload(this, "${payload}")'>${buttonLabel}</button>
              ${sideLabel}
            </div>
          `;
        }).join('');
        const trackClass = capacityView === 'quarter'
          ? 'cap-pill-track quarter-micro'
          : (subunitsPerCol > 1 ? 'cap-pill-track subdivided' : 'cap-pill-track');
        return `<div class='${trackClass}' style='--cap-subunits-per-col:${subunitsPerCol};grid-template-columns: repeat(${totalSubunits}, minmax(0, 1fr)); width: calc(${capacityColumns.length} * var(--capacity-time-col-width));'>${pills}</div>`;
      }).join('');

      return `
        <tr class='cap-pill-row'>
          <td><div class='cap-pill-label'>Assigned items timeline</div></td>
          <td class='cap-pill-cell' colspan='${capacityColumns.length}'>
            <div class='cap-pill-lane'>${tracks}</div>
          </td>
        </tr>
      `;
    }

    function closeCapacityPopover() {
      const pop = document.getElementById('capacityCellPopover');
      if (pop) {
        pop.classList.add('hidden');
        pop.innerHTML = '';
      }
      capacitySelectedCell = null;
    }

    function renderCapacityDetailPanel(cell, userName, weekLabel) {
      const panel = document.getElementById('capacityDetail');
      if (!panel) return;
      if (!cell || !cell.items || !cell.items.length) {
        panel.classList.add('hidden');
        panel.innerHTML = '';
        return;
      }
      panel.classList.remove('hidden');
      panel.innerHTML = `
        <div class='section-head'>
          <h4 style='margin:0;'>Assigned Items · ${userName} · ${weekLabel}</h4>
          <button onclick='clearCapacityDetail()'>Close</button>
        </div>
        <table>
          <thead><tr><th>Step</th><th>Campaign</th><th>Deliverable</th><th>Due</th><th>Waiting</th></tr></thead>
          <tbody>
            ${cell.items.map(i => `
              <tr>
                <td>${i.step_name}</td>
                <td>${i.campaign_id || '-'}</td>
                <td>${i.deliverable_title || '-'}</td>
                <td>${i.due || '-'}</td>
                <td>${i.waiting_on_type || '-'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    function clearCapacityDetail() {
      const panel = document.getElementById('capacityDetail');
      if (panel) {
        panel.classList.add('hidden');
        panel.innerHTML = '';
      }
    }

    function openCapacityCellPopover(buttonEl, userId, columnKey) {
      if (!capacityMatrixData) return;
      const user = (capacityMatrixData.users || []).find(u => u.user_id === userId);
      const column = (capacityColumns || []).find(w => w.key === columnKey);
      const cell = (capacityDisplayCells || {})[capacityCellKey(userId, columnKey)];
      const pop = document.getElementById('capacityCellPopover');
      if (!pop || !cell || !cell.items_total || !user || !column) return;
      const rect = buttonEl.getBoundingClientRect();
      if (cell.items_total === 1 && Array.isArray(cell.items) && cell.items[0]) {
        openItemPopoverByPayload(buttonEl, encodePopoverPayload(capacityItemModulePayload(cell.items[0])));
        return;
      }
      const previewRows = (cell.items || []).map(i => `
        <div class='cap-pop-item'>
          <div><strong>${i.step_name}</strong></div>
          <div class='cap-meta'>${i.campaign_id || '-'} · ${i.deliverable_title || '-'} · Due ${i.due || '-'}</div>
          <div class='actions'>
            <button onclick='openItemPopoverByPayload(this, "${encodePopoverPayload(capacityItemModulePayload(i))}")'>View Item</button>
          </div>
        </div>
      `).join('');
      pop.innerHTML = `
        <div class='cap-popover-header'>
          <strong>${user.user_name} · ${column.label}</strong>
          <button onclick='closeCapacityPopover()'>Close</button>
        </div>
        <div class='cap-popover-list'>${previewRows || "<div class='sub'>No items.</div>"}</div>
        <button class='primary' onclick='window.location.href="/capacity"'>Open Capacity View</button>
      `;
      pop.classList.remove('hidden');
      positionPopoverNear(pop, rect);
      requestAnimationFrame(() => positionPopoverNear(pop, rect));
      capacitySelectedCell = { userId, columnKey };
    }

    function openCapacityFullItems(userId, columnKey) {
      if (!capacityMatrixData) return;
      const user = (capacityMatrixData.users || []).find(u => u.user_id === userId);
      const column = (capacityColumns || []).find(c => c.key === columnKey);
      const cell = (capacityDisplayCells || {})[capacityCellKey(userId, columnKey)];
      if (!user || !cell) return;
      renderCapacityDetailPanel(cell, user.user_name, column?.label || columnKey);
      closeCapacityPopover();
    }

    function buildCapacityColumnsAndCells(data) {
      const rawWeeks = data.weeks || [];
      const rawBuckets = data.buckets || [];
      const rawCells = data.cells || {};
      capacityQuarterWeekSlots = {};
      if (capacityGranularity === 'day') {
        const cols = rawBuckets
          .filter(b => b.bucket_type === 'day')
          .map(b => ({ key: b.bucket_start, label: shortDayLabel(b.bucket_start), week_starts: [b.bucket_start] }));
        return { columns: cols, displayCells: rawCells };
      }
      if (capacityView === 'quarter') {
        const monthGroups = [];
        const monthMap = {};
        for (const w of rawWeeks) {
          const monthKey = monthKeyFromIso(w.week_start);
          if (!monthMap[monthKey]) {
            monthMap[monthKey] = { key: monthKey, label: monthLabelFromKey(monthKey), week_starts: [] };
            monthGroups.push(monthMap[monthKey]);
          }
          const weekSlot = monthMap[monthKey].week_starts.length;
          monthMap[monthKey].week_starts.push(w.week_start);
          capacityQuarterWeekSlots[w.week_start] = { monthKey, weekSlot };
        }

        const userIds = (data.users || []).map(u => u.user_id);
        const displayCells = {};
        for (const userId of userIds) {
          for (const month of monthGroups) {
            const aggregate = {
              capacity_hours: 0,
              forecast_planned_hours: 0,
              active_planned_hours: 0,
              is_over_capacity: false,
              override_requested: false,
              override_approved: false,
              items_preview: [],
              items_total: 0,
              items: [],
            };
            const seen = new Set();
            for (const wk of month.week_starts) {
              const cell = rawCells[capacityCellKey(userId, wk)];
              if (!cell) continue;
              aggregate.capacity_hours += Number(cell.capacity_hours || 0);
              aggregate.forecast_planned_hours += Number(cell.forecast_planned_hours || 0);
              aggregate.active_planned_hours += Number(cell.active_planned_hours || 0);
              aggregate.override_requested = aggregate.override_requested || !!cell.override_requested;
              aggregate.override_approved = aggregate.override_approved || !!cell.override_approved;
              for (const item of (cell.items || [])) {
                if (seen.has(item.step_id)) continue;
                seen.add(item.step_id);
                aggregate.items.push(item);
              }
            }
            aggregate.is_over_capacity = aggregate.forecast_planned_hours > aggregate.capacity_hours && aggregate.capacity_hours > 0;
            aggregate.items_total = aggregate.items.length;
            aggregate.items_preview = aggregate.items.slice(0, 3);
            displayCells[capacityCellKey(userId, month.key)] = aggregate;
          }
        }
        return { columns: monthGroups, displayCells };
      }
      const cols = rawWeeks.map(w => ({ key: w.week_start, label: shortWcLabel(w.week_start), week_starts: [w.week_start] }));
      return { columns: cols, displayCells: rawCells };
    }

    async function renderCapacity() {
      if (!capacityStartWeek) capacityStartWeek = shiftIsoWeeks(isoDate(new Date()), 0);
      const queryGranularity = capacityView === 'day' ? 'day' : 'week';
      const queryWeeks = capacityView === 'quarter' ? 13 : (capacityView === 'day' ? 1 : 4);
      capacityGranularity = queryGranularity;
      capacityWeeks = queryWeeks;
      const q = new URLSearchParams({
        weeks: String(queryWeeks),
        granularity: queryGranularity,
        start_week: capacityStartWeek,
        include_items: capacityShowItems ? 'true' : 'false',
      });
      if (currentActorId) q.set('actor_user_id', String(currentActorId));
      const actorSeniority = String(currentActorIdentity?.seniority || '').toLowerCase();
      if (actorSeniority === 'manager') {
        q.set('team_scope', 'managed');
      }
      const data = await api(`/api/capacity/matrix?${q.toString()}`);
      capacityMatrixData = data;
      capacityStartWeek = data.start_week;

      const table = document.getElementById('capacityMatrixTable');
      const users = data.users || [];
      const mapped = buildCapacityColumnsAndCells(data);
      capacityColumns = mapped.columns;
      capacityDisplayCells = mapped.displayCells;
      const rangeLabel = document.getElementById('capacityRangeLabel');
      if (rangeLabel && capacityColumns.length) {
        if (capacityView === 'day') {
          rangeLabel.textContent = `W/C ${capacityColumns[0].label} → ${capacityColumns[capacityColumns.length - 1].label}`;
        } else {
          rangeLabel.textContent = `${capacityColumns[0].label} → ${capacityColumns[capacityColumns.length - 1].label}`;
        }
      }

      const colgroup = `
        <colgroup>
          <col class='cap-col-user' />
          ${capacityColumns.map(() => "<col class='cap-col-time' />").join('')}
        </colgroup>
      `;
      let thead = '';
      if (capacityView === 'quarter') {
        thead = `
          <thead>
            <tr>
              <th>User</th>
              ${capacityColumns.map(w => `<th>${w.label}</th>`).join('')}
            </tr>
          </thead>
        `;
      } else {
        thead = `
          <thead>
            <tr>
              <th>User</th>
              ${capacityColumns.map(w => `<th>${w.label}</th>`).join('')}
            </tr>
          </thead>
        `;
      }
      const rowsHtml = users.map(user => {
        const userName = String(user?.user_name || '').trim() || '-';
        const userId = String(user?.user_id || '').trim();
        const userNameHtml = userId
          ? `<button type='button' class='cap-user-name-btn' onclick="openObjectPanelChild('user', '${userId.replace(/'/g, '&#39;')}', '')">${escapeHtml(userName)}</button>`
          : `<strong>${escapeHtml(userName)}</strong>`;
        const rowCells = capacityColumns.map(column => {
          const cell = capacityDisplayCells[capacityCellKey(user.user_id, column.key)] || {
            capacity_hours: 0,
            forecast_planned_hours: 0,
            active_planned_hours: 0,
            items_preview: [],
            items_total: 0,
          };
          const preview = capacityShowItems
            ? (cell.items_preview || []).slice(0, 2).map(i => `<div class='cap-preview-line'>${i.step_name}</div>`).join('')
            : '';
          const more = capacityShowItems && cell.items_total > 2 ? `<div class='cap-preview-more'>+${cell.items_total - 2} more</div>` : '';
          const click = cell.items_total ? `onclick='openCapacityCellPopover(this, "${user.user_id}", "${column.key}")'` : '';
          const tdClass = capacityCellClass(cell);
          const forecastHours = Number(cell.forecast_planned_hours || 0);
          const capacityHours = Number(cell.capacity_hours || 0);
          const utilizationPct = capacityHours > 0 ? Math.max(0, Math.min(100, (forecastHours / capacityHours) * 100)) : 0;
          const utilizationLabel = `${Math.round(utilizationPct)}% capacity used`;
          return `
            <td class='${tdClass}'>
              <button class='cap-cell-btn' ${click}>
                <div class='cap-main'>
                  <span class='cap-hours'>${forecastHours.toFixed(1)} / ${capacityHours.toFixed(1)}h</span>
                  <span class='cap-main-right'>
                    <span class='cap-donut' style='--cap-pct:${utilizationPct.toFixed(1)};' title='${utilizationLabel}' aria-label='${utilizationLabel}'></span>
                    ${capStatusChip(cell)}
                  </span>
                </div>
                <div class='cap-meta'>Active ${Number(cell.active_planned_hours || 0).toFixed(1)}h</div>
                ${capacityShowItems ? `<div class='cap-preview'>${preview}${more}</div>` : ''}
              </button>
            </td>
          `;
        }).join('');
        const summaryRow = `
          <tr>
            <td>
              <div class='cap-user'>
                ${userNameHtml}
                <div class='cap-meta'>${user.primary_role}</div>
                <div class='cap-meta'>Forecast ${Number(user.totals.forecast_hours || 0).toFixed(1)}h · Cap ${Number(user.totals.capacity_hours || 0).toFixed(1)}h</div>
              </div>
            </td>
            ${rowCells}
          </tr>
        `;
        return summaryRow;
      }).join('');
      const emptyColSpan = capacityColumns.length + 1;
      const fallbackRow = `<tr><td class='sub' colspan='${emptyColSpan}'>No capacity rows in this window.</td></tr>`;
      table.innerHTML = `${colgroup}${thead}<tbody>${rowsHtml || fallbackRow}</tbody>`;

      const weekBtn = document.getElementById('capacityWeekBtn');
      const monthBtn = document.getElementById('capacityMonthBtn');
      const quarterBtn = document.getElementById('capacityQuarterBtn');
      if (weekBtn) weekBtn.classList.toggle('primary', capacityView === 'day');
      if (monthBtn) monthBtn.classList.toggle('primary', capacityView === 'month');
      if (quarterBtn) quarterBtn.classList.toggle('primary', capacityView === 'quarter');
      closeCapacityPopover();
      clearCapacityDetail();
      return data.items || [];
    }

    function setCapacityView(view) {
      if (view === 'day') {
        capacityView = 'day';
        capacityGranularity = 'day';
        capacityWeeks = 1;
      } else if (view === 'quarter') {
        capacityView = 'quarter';
        capacityGranularity = 'week';
        capacityWeeks = 13;
      } else {
        capacityView = 'month';
        capacityGranularity = 'week';
        capacityWeeks = 4;
      }
      renderCapacity().catch(err => log('Capacity render failed', String(err)));
    }

    function shiftCapacityWindow(direction) {
      const dir = direction < 0 ? -1 : 1;
      if (capacityView === 'day') {
        const visibleAnchor = (capacityColumns && capacityColumns.length && capacityColumns[0].key)
          ? capacityColumns[0].key
          : null;
        const anchor = visibleAnchor || capacityStartWeek || isoDate(new Date());
        capacityStartWeek = shiftIsoDays(anchor, 7 * dir);
      } else {
        const anchor = capacityStartWeek || isoDate(new Date());
        const stepWeeks = capacityView === 'quarter' ? 13 : 4;
        capacityStartWeek = shiftIsoWeeks(anchor, stepWeeks * dir);
      }
      renderCapacity().catch(err => log('Capacity render failed', String(err)));
    }

    function snapCapacityToToday() {
      capacityStartWeek = shiftIsoWeeks(isoDate(new Date()), 0);
      renderCapacity().catch(err => log('Capacity render failed', String(err)));
    }

    function toggleCapacityItems() {
      capacityShowItems = !!document.getElementById('capacityShowItems')?.checked;
      renderCapacity().catch(err => log('Capacity render failed', String(err)));
    }

    async function renderSystemRisks() {
      const data = await api('/api/risks/system');
      const body = document.getElementById('risksBody');
      body.innerHTML = data.items.slice(0, 12).map(r => `
        <tr>
          <td>${r.severity}</td>
          <td><code>${r.risk_code}</code></td>
          <td>${r.is_open ? "<span class='tag risk'>open</span>" : "<span class='tag ok'>closed</span>"}</td>
        </tr>
      `).join('') || `<tr><td colspan='3' class='sub'>No system risks.</td></tr>`;
      return data.items;
    }

    async function renderHealthWarnings() {
      const data = await api('/api/campaigns/health?limit=500&offset=0');
      const warnings = [];
      for (const campaign of (data.items || [])) {
        for (const warning of (campaign.warnings || [])) {
          warnings.push({
            campaign_id: campaign.campaign_id,
            campaign_title: campaign.title,
            type: warning.type,
            severity: warning.severity,
            reason: warning.reason,
            owner_user_id: warning.owner_user_id || null,
          });
        }
      }
      const body = document.getElementById('healthWarningsBody');
      body.innerHTML = warnings.slice(0, 40).map(w => `
        <tr>
          <td>${w.campaign_id} · ${w.campaign_title}</td>
          <td>${w.type}</td>
          <td>${healthChip(w.severity)}</td>
          <td>${w.reason}</td>
          <td>${userName(w.owner_user_id)}</td>
        </tr>
      `).join('') || `<tr><td colspan='5' class='sub'>No capacity/compression warnings.</td></tr>`;
      const count = document.getElementById('healthWarningsCount');
      if (count) count.textContent = `${warnings.length} open warnings`;
      return warnings;
    }

    async function renderManualRisks() {
      const data = await api('/api/risks/manual');
      const body = document.getElementById('manualRisksBody');
      body.innerHTML = data.items.slice(0, 12).map(r => `
        <tr>
          <td><code>${r.id}</code></td>
          <td>${r.severity}</td>
          <td>${r.is_open ? "<span class='tag risk'>open</span>" : "<span class='tag ok'>closed</span>"}</td>
          <td>${r.details}</td>
        </tr>
      `).join('') || `<tr><td colspan='4' class='sub'>No manual risks.</td></tr>`;
      return data.items;
    }

    async function renderDeliverableHistory() {
      const deliverables = await api('/api/deliverables');
      const target = deliverables.items.find(d => d.id === selectedDeliverableId) || deliverables.items[0];
      const activityBody = document.getElementById('activityBody');
      const reviewsBody = document.getElementById('reviewsBody');
      const header = document.getElementById('historyHeader');

      if (!target) {
        header.textContent = 'No deliverables available yet.';
        activityBody.innerHTML = `<div class='sub'>No activity.</div>`;
        reviewsBody.innerHTML = `<div class='sub'>No review flags.</div>`;
        return;
      }

      const history = await api(`/api/deliverables/${target.id}/history`);
      selectedDeliverableId = target.id;
      header.textContent = `${history.deliverable.id} · ${history.deliverable.title} · ${history.deliverable.status}`;

      activityBody.innerHTML = history.activity.slice(0, 20).map(a => {
        const action = String(a.action || '').toLowerCase();
        const tone = action.includes('risk') || action.includes('blocked')
          ? 'risk'
          : (action.includes('review') || action.includes('approve') ? 'review' : (action.includes('complete') ? 'done' : 'info'));
        const note = (a.meta && a.meta.comment) ? a.meta.comment : (a.meta?.status || 'No additional note');
        return `
          <article class='activity-item'>
            <div class='activity-dot ${tone}'></div>
            <div>
              <div class='activity-card-title'>${(a.action || '').replaceAll('_', ' ')}</div>
              <div class='activity-card-meta'>${niceDate(a.created_at)}</div>
              <div>${note}</div>
            </div>
          </article>
        `;
      }).join('') || `<div class='sub'>No activity events.</div>`;

      reviewsBody.innerHTML = history.reviews.slice(0, 20).map(r => {
        const status = String(r.status || '').toLowerCase();
        const severity = status.includes('changes') || status.includes('rejected')
          ? 'high'
          : (status.includes('pending') || status.includes('awaiting') ? 'medium' : 'low');
        const severityLabel = severity === 'high' ? 'High' : (severity === 'medium' ? 'Medium' : 'Low');
        const title = `${String(r.review_type || 'Review').replaceAll('_', ' ')} ${status.includes('changes') ? 'requires changes' : status.replaceAll('_', ' ')}`;
        return `
          <article class='risk-flag ${severity}'>
            <div class='risk-flag-head'>
              <span>${title}</span>
              <span>${severityLabel}</span>
            </div>
            <div>${r.comments || 'No reviewer comment provided.'}</div>
            <div class='activity-card-meta'>${niceDate(r.created_at)}</div>
          </article>
        `;
      }).join('') || `<div class='sub'>No review events.</div>`;
    }

    async function refreshAll() {
      await refreshRoleMode();
      await renderScreen();
      requestAnimationFrame(() => applyModuleLayoutRules());
    }

    async function refreshRoleMode() {
      try {
        const selector = document.getElementById('roleMode');
        const actor = String(selector?.value || '').trim();
        const actorUser = usersById[actor];
        if (!actor || !actorUser) {
          throw new Error('No valid user selected');
        }
        const role = effectiveRoleForUser(actorUser);
        const data = await api(`/api/dashboard/role?role=${role}&actor_user_id=${actor}`);
        const roleFlagsEl = document.getElementById('roleFlags');
        if (roleFlagsEl) {
          const flags = Object.entries(data.flags).filter(([_, v]) => v).map(([k]) => k.replace('show_', '')).join(', ');
          roleFlagsEl.textContent = `${actorUser.name || 'User'} · ${labelRole(role)} · Enabled panels: ${flags || 'basic'}`;
        }
        currentRoleFlags = data.flags;
        currentRoleControls = new Set(data.controls || []);
        currentRole = role;
        currentActorId = actor;
        currentActorIdentity = data.identity || currentActorIdentity;
        try {
          if (role === 'head_ops' || role === 'admin') {
            await loadRolePermissions();
          }
        } catch (_) {
          // Keep default static permissions if role matrix cannot be loaded.
        }
        try {
          demoRailMinimised = localStorage.getItem(demoRailStorageKey()) === '1';
        } catch (_) {
          demoRailMinimised = false;
        }
        localStorage.setItem('roleMode', actor);
        renderNavActive();
        applyRoleVisibility();
      } catch (err) {
        log('Role mode failed', String(err));
      }
    }

    async function renderScreen() {
      const screen = currentScreen;
      applyScreenLayoutMode();
      const allowed = canViewScreen(screen);
      const notAllowed = document.getElementById('sectionNotAllowed');
      if (notAllowed) notAllowed.classList.toggle('hidden', allowed);
      if (!allowed) return;
      try {
        if (screen === 'home') {
          await Promise.all([renderSummary(), renderMyWork(currentRole, currentActorId)]);
          return;
        }
        if (screen === 'my-work') {
          await renderMyWork(currentRole, currentActorId);
          return;
        }
        if (screen === 'deals') {
          await renderDeals();
          return;
        }
        if (screen === 'people') {
          await renderPeople();
          return;
        }
        if (screen === 'campaigns') {
          await renderCampaigns();
          return;
        }
        if (screen === 'gantt') {
          await renderGantt();
          return;
        }
        if (screen === 'reviews') {
          await Promise.all([renderReviewsQueue(), renderDeliverableHistory()]);
          return;
        }
        if (screen === 'risks') {
          await Promise.all([renderSystemRisks(), renderHealthWarnings(), renderManualRisks()]);
          return;
        }
        if (screen === 'capacity') {
          await renderCapacity();
          return;
        }
        if (screen === 'admin') {
          await Promise.all([renderOpsDefaults(), renderCardModuleSettings(), renderListModuleSettings(), renderRolePermissionsEditor(), renderAdminUsers(), renderObjectRelationships()]);
          return;
        }
      } finally {
        requestAnimationFrame(() => applyModuleLayoutRules());
      }
    }

    function applyControlVisibility() {
      const demoRail = document.getElementById('demoRail');
      const railToggle = document.getElementById('demoRailToggle');
      const minimiseBtn = document.getElementById('demoRailMinimiseBtn');
      const railAllowed = !!UI_FLAGS.show_demo_rail && (UI_FLAGS.demo_rail_allowed_roles || []).includes(currentRole);
      const canMinimise = currentRole === 'head_ops';
      if (demoRail) {
        demoRail.classList.toggle('hidden', !railAllowed);
        demoRail.classList.toggle('demo-rail-collapsed', railAllowed && canMinimise && demoRailMinimised);
      }
      if (railToggle) {
        const showToggle = railAllowed && canMinimise && demoRailMinimised;
        railToggle.classList.toggle('hidden', !showToggle);
        railToggle.classList.toggle('visible', showToggle);
      }
      if (minimiseBtn) {
        minimiseBtn.classList.toggle('hidden', !(railAllowed && canMinimise && !demoRailMinimised));
      }

      document.querySelectorAll('[data-control]').forEach(el => {
        const id = el.getAttribute('data-control');
        const visible = canUseControl(id, currentRole);
        const wrappedCard = el.closest('.demo-card');
        el.classList.toggle('hidden', !visible);
        el.setAttribute('aria-hidden', visible ? 'false' : 'true');
        if (wrappedCard) {
          const active = wrappedCard.querySelector('[data-control]:not(.hidden)');
          wrappedCard.classList.toggle('hidden', !active || !railAllowed);
        }
      });
    }

    function applyRoleVisibility() {
      const flags = currentRoleFlags || {};
      const screenAllowed = canViewScreen(currentScreen);
      const screenSections = {
        home: ['sectionControls', 'kpis', 'sectionMyWork'],
        'my-work': ['sectionControls', 'sectionMyWork'],
        deals: ['sectionControls', 'sectionActions', 'sectionDeals'],
        people: ['sectionPeople'],
        campaigns: ['sectionControls', 'sectionCampaigns'],
        gantt: ['sectionControls', 'sectionGantt'],
        reviews: ['sectionControls', 'sectionReviews', 'sectionHistory'],
        risks: ['sectionControls', 'sectionCapacityRisk', 'sectionSystemRisks', 'sectionHealthWarnings', 'sectionRiskConsole'],
        capacity: ['sectionCapacity'],
        admin: ['sectionControls', 'sectionOpsDefaults', 'sectionCardModules', 'sectionListModules', 'sectionRolePermissions', 'sectionAdminUsers', 'sectionObjectRelationships'],
      };
      const all = [
        'sectionControls',
        'kpis',
        'sectionNotAllowed',
        'sectionMyWork',
        'sectionActions',
        'sectionDeals',
        'sectionPeople',
        'sectionCampaigns',
        'sectionGantt',
        'sectionReviews',
        'sectionDeliverables',
        'sectionHistory',
        'sectionSteps',
        'sectionOpsDefaults',
        'sectionCardModules',
        'sectionListModules',
        'sectionRolePermissions',
        'sectionAdminUsers',
        'sectionObjectRelationships',
        'sectionCapacityRisk',
        'sectionCapacity',
        'sectionSystemRisks',
        'sectionHealthWarnings',
        'sectionRiskConsole',
      ];
      if (!screenAllowed && currentScreen === 'admin') {
        for (const id of all) {
          const el = document.getElementById(id);
          if (!el) continue;
          el.classList.add('hidden');
        }
        applyControlVisibility();
        return;
      }
      const allowed = new Set(screenSections[currentScreen] || []);
      const map = all.map(id => [id, allowed.has(id)]);
      if (currentScreen === 'deals' && flags.show_deals_pipeline === false) {
        map.push(['sectionDeals', false]);
      }
      if (currentScreen === 'risks' && !flags.show_risks) {
        map.push(['sectionSystemRisks', false], ['sectionHealthWarnings', false], ['sectionRiskConsole', false]);
      }
      if (currentScreen === 'capacity' && !flags.show_capacity) {
        map.push(['sectionCapacity', false]);
      }
      if (!canUseControl('create_deal', currentRole)) {
        map.push(['sectionActions', false]);
      }
      if (!flags.show_risks && currentScreen === 'risks') {
        map.push(['sectionHealthWarnings', false], ['sectionRiskConsole', false]);
      }
      for (const [id, visible] of map) {
        const el = document.getElementById(id);
        if (!el) continue;
        el.classList.toggle('hidden', !visible);
      }
      applyQuickFilterVisibility();
      applyControlVisibility();
    }

    function setFilterPairVisibility(selectId, visible) {
      const selectEl = document.getElementById(selectId);
      const labelEl = document.querySelector(`label[for='${selectId}']`);
      if (selectEl) selectEl.classList.toggle('hidden', !visible);
      if (labelEl) labelEl.classList.toggle('hidden', !visible);
    }

    function applyQuickFilterVisibility() {
      const screen = String(currentScreen || '').toLowerCase();
      setFilterPairVisibility('qScopeHealth', screen === 'deals');
      setFilterPairVisibility('qCampaignHealth', screen === 'campaigns');
    }

    function selectDeliverableForHistory(deliverableId) {
      if (currentScreen !== 'reviews') {
        if (!canViewScreen('reviews')) {
          toast('Reviews/History is not available for this role.', 'error');
          return;
        }
        window.location.href = reviewsPathWithDeliverable(deliverableId);
        return;
      }
      selectedDeliverableId = deliverableId;
      const select = document.getElementById('historyDeliverableSelect');
      if (select) select.value = deliverableId;
      renderDeliverableHistory().catch(err => log('History render failed', String(err)));
      const section = document.getElementById('sectionHistory');
      if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function onHistorySelectionChange() {
      const select = document.getElementById('historyDeliverableSelect');
      selectedDeliverableId = select.value || null;
      renderDeliverableHistory().catch(err => log('History render failed', String(err)));
    }

    function matchesUserRole(user, role) {
      return effectiveRoleForUser(user) === role;
    }

    function matchesUserTeam(user, team) {
      return String(user?.primary_team || '').toLowerCase() === String(team || '').toLowerCase();
    }

    function matchesUserSeniority(user, level) {
      return String(user?.seniority || '').toLowerCase() === String(level || '').toLowerCase();
    }

    function selectPreferredUser(candidates) {
      if (!Array.isArray(candidates) || !candidates.length) return null;
      const activeId = String(currentActorId || '').trim();
      if (activeId) {
        const exact = candidates.find(user => String(user?.id || '') === activeId);
        if (exact) return exact;
      }
      return candidates[0];
    }

    async function getDemoUsers() {
      if (!Array.isArray(usersDirectory) || usersDirectory.length === 0) {
        await loadUsersDirectory();
      }
      const users = Array.isArray(usersDirectory) ? usersDirectory : [];
      const byRole = role => users.filter(user => matchesUserRole(user, role));
      const byTeam = team => users.filter(user => matchesUserTeam(user, team));
      const byTeamAndSeniority = (team, seniority) => users.filter(
        user => matchesUserTeam(user, team) && matchesUserSeniority(user, seniority),
      );

      const amUser = selectPreferredUser(byRole('am')) || selectPreferredUser(byTeam('sales'));
      const cmUser = selectPreferredUser(byRole('cm')) || selectPreferredUser(byTeam('client_services'));
      const ccUser = selectPreferredUser(byRole('cc')) || selectPreferredUser(byTeam('editorial'));
      const salesLead = selectPreferredUser(byRole('head_sales')) || selectPreferredUser(byTeamAndSeniority('sales', 'leadership'));
      const opsLead = selectPreferredUser(byRole('head_ops'))
        || selectPreferredUser(byRole('admin'))
        || selectPreferredUser(byRole('cm'))
        || selectPreferredUser(byTeamAndSeniority('client_services', 'leadership'))
        || selectPreferredUser(byTeam('client_services'));

      const resolved = {
        am: amUser?.id || null,
        ops: opsLead?.id || null,
        cm: cmUser?.id || null,
        cc: ccUser?.id || null,
        sales: salesLead?.id || amUser?.id || null,
      };

      const required = ['am', 'ops', 'cm', 'cc', 'sales'];
      const missing = required.filter(key => !resolved[key]);
      if (missing.length > 0) {
        throw new Error(`Unable to infer demo actors from active users: missing ${missing.join(', ')}`);
      }
      return resolved;
    }

    function buildDealPayload() {
      const actorId = String(currentActorId || '').trim();
      if (!actorId) throw new Error('No active actor selected');
      const payload = {
        client_name: document.getElementById('dealClientName').value.trim(),
        brand_publication: document.getElementById('dealPublication').value,
        am_user_id: actorId,
        sow_start_date: document.getElementById('dealSowStart').value,
        sow_end_date: document.getElementById('dealSowEnd').value,
        icp: document.getElementById('dealICP').value.trim(),
        campaign_objective: document.getElementById('dealObjective').value.trim(),
        messaging_positioning: document.getElementById('dealMessaging').value.trim(),
        client_contacts: collectContacts(),
        attachments: collectAttachments(),
        product_lines: collectProductLines(),
      };
      if (!payload.client_name) throw new Error('Client is required.');
      if (!payload.sow_start_date || !payload.sow_end_date) throw new Error('SOW start and end dates are required.');
      if (!payload.icp || !payload.campaign_objective || !payload.messaging_positioning) {
        throw new Error('ICP, objective, and messaging are required.');
      }
      if (!payload.product_lines.length) throw new Error('At least one product line is required.');
      return payload;
    }

    async function submitNewDeal(event) {
      if (event) event.preventDefault();
      try {
        const actorId = String(currentActorId || '').trim();
        if (!actorId) throw new Error('No active actor selected');
        const payload = buildDealPayload();
        const result = await api(`/api/deals?actor_user_id=${encodeURIComponent(actorId)}`, { method: 'POST', body: JSON.stringify(payload) });
        log('Scope created', result);
        toast(`Created ${result.id}`, 'success');
        await refreshAll();
      } catch (err) {
        log('Create scope failed', String(err));
      }
    }

    async function submitAndRouteLatestDeal() {
      try {
        const actorId = String(currentActorId || '').trim();
        if (!actorId) throw new Error('No active actor selected');
        const payload = buildDealPayload();
        const created = await api(`/api/deals?actor_user_id=${encodeURIComponent(actorId)}`, { method: 'POST', body: JSON.stringify(payload) });
        const submitted = await api(`/api/deals/${created.id}/submit?actor_user_id=${encodeURIComponent(actorId)}`, { method: 'POST' });
        log('Scope created + submitted', submitted);
        toast(`Submitted ${submitted.id} to Ops`, 'success');
        await refreshAll();
      } catch (err) {
        log('Create+submit failed', String(err));
      }
    }

    async function createDemoDeal() {
      try {
        const payload = {
          client_name: 'UI Demo Client',
          brand_publication: 'uc_today',
          am_user_id: (await getDemoUsers()).am,
          sow_start_date: '2026-04-07',
          sow_end_date: '2027-04-01',
          icp: 'Enterprise B2B buyers',
          campaign_objective: 'Increase visibility',
          messaging_positioning: 'Thought leadership narrative',
          client_contacts: [],
          attachments: [],
          product_lines: [{ product_type: 'demand', tier: 'silver', options_json: {} }],
        };
        const u = await getDemoUsers();
        const result = await api(`/api/deals?actor_user_id=${u.am}`, { method: 'POST', body: JSON.stringify(payload) });
        await api(`/api/deals/${result.id}/submit?actor_user_id=${u.am}`, { method: 'POST' });
        log('Scope created', result);
        await refreshAll();
      } catch (err) { log('Create scope failed', String(err)); }
    }

    async function latestDealId() {
      const deals = await api('/api/deals');
      if (!deals.items.length) throw new Error('No scopes found. Create a demo scope first.');
      return deals.items[0].id;
    }

    function firstUserIdForTeam(team) {
      const match = (usersDirectory || []).find(u => String(u.primary_team || '').toLowerCase() === String(team || '').toLowerCase());
      return match ? match.id : null;
    }

    async function approveScope(scopeId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        if (!canApproveScopes()) throw new Error('You do not have permission to approve scopes');
        const scopes = await api('/api/scopes');
        const scope = (scopes.items || []).find(s => String(s.id) === String(scopeId));
        if (!scope) throw new Error('Scope not found');
        const cmUserId = scope.assigned_cm_user_id || firstUserIdForTeam('client_services');
        const ccUserId = scope.assigned_cc_user_id || firstUserIdForTeam('editorial');
        if (!cmUserId || !ccUserId) {
          throw new Error('Scope approval requires assigned CM and CC (or available users in Client Services and Editorial).');
        }
        await api(`/api/scopes/${encodeURIComponent(scopeId)}/ops-approve?actor_user_id=${encodeURIComponent(currentActorId)}`, {
          method: 'POST',
          body: JSON.stringify({
            head_ops_user_id: currentActorId,
            cm_user_id: cmUserId,
            cc_user_id: ccUserId,
            ccs_user_id: scope.assigned_ccs_user_id || null,
          }),
        });
        toast(`Scope ${scopeId} approved`, 'success');
        await Promise.all([renderDeals(), renderSummary(), renderCampaigns()]);
      } catch (err) {
        toast(`Scope approval failed: ${String(err)}`, 'error');
        log('Scope approval failed', String(err));
      }
    }

    async function generateCampaignsForScope(scopeId) {
      try {
        if (!currentActorId) throw new Error('No active actor selected');
        if (!canGenerateScopeCampaigns()) throw new Error('You do not have permission to generate campaigns');
        await api(`/api/scopes/${encodeURIComponent(scopeId)}/generate-campaigns?actor_user_id=${encodeURIComponent(currentActorId)}`, {
          method: 'POST',
        });
        toast(`Campaigns generated for ${scopeId}`, 'success');
        await Promise.all([renderDeals(), renderCampaigns(), renderSummary()]);
      } catch (err) {
        toast(`Campaign generation failed: ${String(err)}`, 'error');
        log('Scope campaign generation failed', String(err));
      }
    }

    async function submitLatestDeal() {
      try {
        const u = await getDemoUsers();
        const dealId = await latestDealId();
        const result = await api(`/api/deals/${dealId}/submit?actor_user_id=${u.am}`, { method: 'POST' });
        log('Scope submitted', result);
        await refreshAll();
      } catch (err) { log('Submit failed', String(err)); }
    }

    async function opsApproveLatestDeal() {
      try {
        const u = await getDemoUsers();
        const dealId = await latestDealId();
        const payload = { head_ops_user_id: u.ops, cm_user_id: u.cm, cc_user_id: u.cc };
        const result = await api(`/api/deals/${dealId}/ops-approve?actor_user_id=${u.ops}`, { method: 'POST', body: JSON.stringify(payload) });
        log('Ops approve complete', result);
        await refreshAll();
      } catch (err) { log('Ops approve failed', String(err)); }
    }

    async function generateLatestDealCampaigns() {
      try {
        const u = await getDemoUsers();
        const dealId = await latestDealId();
        const result = await api(`/api/deals/${dealId}/generate-campaigns?actor_user_id=${u.ops}`, { method: 'POST' });
        log('Campaigns generated', result);
        await refreshAll();
      } catch (err) { log('Generation failed', String(err)); }
    }

    async function latestDeliverableId() {
      const deliverables = await api('/api/deliverables');
      if (!deliverables.items.length) throw new Error('No deliverables yet. Generate campaigns first.');
      return deliverables.items[0].id;
    }

    async function markAnyReadyToPublish() {
      try {
        const u = await getDemoUsers();
        const deliverableId = await latestDeliverableId();
        const result = await api(`/api/deliverables/${deliverableId}/ready-to-publish?actor_user_id=${u.cc}`, { method: 'POST' });
        log('Marked ready_to_publish', result);
        await refreshAll();
      } catch (err) { log('Ready to publish failed', String(err)); }
    }

    async function completeNextWorkflowStep() {
      try {
        const u = await getDemoUsers();
        const steps = await api('/api/workflow-steps');
        const open = steps.items.find(s => !s.actual_done);
        if (!open) throw new Error('No open workflow steps.');
        const actor = open.owner_role === 'cm' ? u.cm : (open.owner_role === 'cc' ? u.cc : u.ops);
        const result = await api(`/api/workflow-steps/${open.id}/complete`, {
          method: 'POST',
          body: JSON.stringify({ actor_user_id: actor }),
        });
        log('Workflow step completed', result);
        await refreshAll();
      } catch (err) { log('Complete step failed', String(err)); }
    }

    async function overrideNextWorkflowStepDue() {
      try {
        const u = await getDemoUsers();
        const steps = await api('/api/workflow-steps');
        const open = steps.items.find(s => !s.actual_done && s.current_due);
        if (!open) throw new Error('No open step with due date.');
        const d = new Date(open.current_due);
        d.setDate(d.getDate() + 1);
        const iso = isoDate(d);
        const result = await api(`/api/workflow-steps/${open.id}/override-due`, {
          method: 'POST',
          body: JSON.stringify({ actor_user_id: u.cm, current_due_iso: iso, reason_code: 'client_delay' }),
        });
        log('Workflow step due overridden', result);
        await refreshAll();
      } catch (err) { log('Override due failed', String(err)); }
    }

    async function runOpsRiskCapacityJob() {
      try {
        let actorId = String(currentActorId || '').trim();
        if (!actorId) {
          const u = await getDemoUsers();
          actorId = String(u.ops || '').trim();
        }
        if (!actorId) throw new Error('No eligible actor available for Ops job.');
        const result = await api(`/api/jobs/run-ops-risk-capacity?actor_user_id=${encodeURIComponent(actorId)}`, { method: 'POST' });
        log('Ops risk/capacity job complete', result);
        await refreshAll();
      } catch (err) { log('Ops job failed', String(err)); }
    }

    function nextDeliverableStatus(current) {
      const sequence = [
        'planned',
        'in_progress',
        'awaiting_internal_review',
        'internal_review_complete',
        'awaiting_client_review',
        'approved',
        'ready_to_publish',
        'scheduled_or_published',
        'complete',
      ];
      const idx = sequence.indexOf(current);
      if (idx === -1 || idx === sequence.length - 1) return null;
      return sequence[idx + 1];
    }

    async function advanceFirstDeliverable() {
      try {
        const u = await getDemoUsers();
        const deliverables = await api('/api/deliverables');
        const first = deliverables.items.find(d => String(d.delivery_status || '').toLowerCase() !== 'complete');
        if (!first) throw new Error('No active deliverables.');
        const target = nextDeliverableStatus(String(first.delivery_status || '').toLowerCase());
        if (!target) throw new Error('No next status available.');
        const actor =
          target.includes('client') ? u.am :
          target === 'internal_review_complete' ? u.cm :
          target === 'ready_to_publish' ? u.cc :
          target === 'complete' ? u.cm :
          u.cc;
        const result = await api(`/api/deliverables/${first.id}/transition`, {
          method: 'POST',
          body: JSON.stringify({ actor_user_id: actor, to_status: target, comment: 'UI transition' }),
        });
        log('Deliverable transitioned', result);
        await refreshAll();
      } catch (err) { log('Deliverable transition failed', String(err)); }
    }

    async function requestCapacityOverride() {
      try {
        const u = await getDemoUsers();
        const rows = await api('/api/capacity-ledger');
        const over = rows.items.find(r => r.is_over_capacity && !r.override_requested);
        if (!over) throw new Error('No over-capacity row available for request.');
        const result = await api(`/api/capacity-ledger/${over.id}/request-override`, {
          method: 'POST',
          body: JSON.stringify({ actor_user_id: u.cm, reason: 'Short-term campaign priority' }),
        });
        log('Capacity override requested', result);
        await refreshAll();
      } catch (err) { log('Request override failed', String(err)); }
    }

    async function approveCapacityOverride() {
      try {
        const u = await getDemoUsers();
        const rows = await api('/api/capacity-ledger');
        const pending = rows.items.find(r => r.override_requested && !r.override_approved);
        if (!pending) throw new Error('No pending override request.');
        const result = await api(`/api/capacity-ledger/${pending.id}/decide-override`, {
          method: 'POST',
          body: JSON.stringify({ actor_user_id: u.ops, approve: true, reason: 'Approved for delivery window' }),
        });
        log('Capacity override approved', result);
        await refreshAll();
      } catch (err) { log('Approve override failed', String(err)); }
    }

    async function createAndApproveSowChange() {
      try {
        const u = await getDemoUsers();
        const campaigns = await api('/api/campaigns');
        if (!campaigns.items.length) throw new Error('No campaigns available.');
        const campaignId = campaigns.items[0].id;

        const req = await api(`/api/campaigns/${campaignId}/sow-change-requests?actor_user_id=${u.cm}`, {
          method: 'POST',
          body: JSON.stringify({ requested_by_user_id: u.cm, impact_scope_json: { timeline: '+5 working days', scope: 'add asset' } })
        });
        await api(`/api/sow-change-requests/${req.id}/decide?actor_user_id=${u.ops}`, {
          method: 'POST',
          body: JSON.stringify({ approver_user_id: u.ops, approver_role: 'head_ops', decision: 'approved' })
        });
        const final = await api(`/api/sow-change-requests/${req.id}/decide?actor_user_id=${u.sales}`, {
          method: 'POST',
          body: JSON.stringify({ approver_user_id: u.sales, approver_role: 'head_sales', decision: 'approved' })
        });
        log('SOW change activated', final);
        await refreshAll();
      } catch (err) { log('SOW flow failed', String(err)); }
    }

    async function createManualRisk() {
      try {
        const u = await getDemoUsers();
        const campaigns = await api('/api/campaigns');
        if (!campaigns.items.length) throw new Error('No campaigns available.');
        const result = await api('/api/risks/manual', {
          method: 'POST',
          body: JSON.stringify({
            actor_user_id: u.cm,
            campaign_id: campaigns.items[0].id,
            severity: 'medium',
            details: 'Manual risk raised from UI console',
          }),
        });
        log('Manual risk created', result);
        await refreshAll();
      } catch (err) { log('Create manual risk failed', String(err)); }
    }

    async function resolveFirstManualRisk() {
      try {
        const u = await getDemoUsers();
        const risks = await api('/api/risks/manual');
        const open = risks.items.find(r => r.is_open);
        if (!open) throw new Error('No open manual risks.');
        const result = await api(`/api/risks/manual/${open.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ actor_user_id: u.cm, is_open: false }),
        });
        log('Manual risk resolved', result);
        await refreshAll();
      } catch (err) { log('Resolve manual risk failed', String(err)); }
    }

    async function resolveFirstEscalation() {
      try {
        const u = await getDemoUsers();
        const escalations = await api('/api/escalations');
        const open = escalations.items.find(e => !e.resolved_at);
        if (!open) throw new Error('No open escalations.');
        const result = await api(`/api/escalations/${open.id}/resolve`, {
          method: 'POST',
          body: JSON.stringify({ actor_user_id: u.ops }),
        });
        log('Escalation resolved', result);
        await refreshAll();
      } catch (err) { log('Resolve escalation failed', String(err)); }
    }

    async function bootstrapApp() {
      const savedViewAs = localStorage.getItem('roleMode');

      const path = window.location.pathname;
      const qs = new URLSearchParams(window.location.search);
      const deliverableFromQuery = qs.get('deliverable');
      if (deliverableFromQuery) {
        selectedDeliverableId = deliverableFromQuery;
      }
      if (path === '/') {
        const savedUser = usersById[savedViewAs || ''];
        const target = defaultScreenForRole(savedUser ? effectiveRoleForUser(savedUser) : 'cm');
        window.location.replace(screenPath(target));
        return;
      }

      await initDealForm();
      await loadUsersDirectory();
      const roleSelect = document.getElementById('roleMode');
      if (savedViewAs && roleSelect && [...roleSelect.options].some(o => o.value === savedViewAs)) {
        roleSelect.value = savedViewAs;
      }
      await refreshRoleMode();
      syncRailAnchors();
      currentScreen = screenFromPath(path);
      currentWorkspaceCampaignId = campaignIdFromPath(path);
      renderNavActive();
      applyScreenLayoutMode();
      applyRoleVisibility();
      await renderScreen();
      requestAnimationFrame(() => applyModuleLayoutRules());
    }

    window.addEventListener('resize', () => {
      syncRailAnchors();
      applyModuleLayoutRules();
      updateGanttBarOverflowLabels();
      keepPopoverInViewport(document.getElementById('capacityCellPopover'));
      keepPillDropdownsInViewport();
    });
    window.addEventListener('orientationchange', () => {
      syncRailAnchors();
      applyModuleLayoutRules();
      updateGanttBarOverflowLabels();
      keepPopoverInViewport(document.getElementById('capacityCellPopover'));
      keepPillDropdownsInViewport();
    });
    document.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (!target.closest('#qUsersDropdown')) {
        closeUsersDropdown();
      }

      const listToggle = target.closest('[data-list-toggle]');
      if (listToggle instanceof HTMLElement) {
        event.preventDefault();
        event.stopPropagation();
        const key = String(listToggle.getAttribute('data-list-toggle') || '').trim();
        if (!key) return;
        toggleListRow(key);
        return;
      }

      const listMenuAction = target.closest('[data-list-menu-action]');
      if (listMenuAction instanceof HTMLElement) {
        event.preventDefault();
        event.stopPropagation();
        const action = String(listMenuAction.getAttribute('data-list-menu-action') || '');
        const moduleType = String(listMenuAction.getAttribute('data-module-type') || '');
        const objectId = String(listMenuAction.getAttribute('data-object-id') || '');
        const campaignId = String(listMenuAction.getAttribute('data-campaign-id') || '');
        closeAllModuleOptionMenus();
        handleListMenuAction(action, moduleType, objectId, campaignId).catch(err => {
          toast(`List action failed: ${String(err)}`, 'error');
        });
        return;
      }

      const listTitleOpen = target.closest('[data-list-open-popover]');
      if (listTitleOpen instanceof HTMLElement) {
        event.preventDefault();
        event.stopPropagation();
        const encoded = String(listTitleOpen.getAttribute('data-list-open-popover') || '').trim();
        if (!encoded) return;
        openItemPopoverByPayload(listTitleOpen, encoded);
        return;
      }

      const panelChildOpen = target.closest('[data-object-panel-child-open]');
      if (panelChildOpen instanceof HTMLElement) {
        event.preventDefault();
        event.stopPropagation();
        const moduleType = String(panelChildOpen.getAttribute('data-module-type') || '').trim();
        const objectId = String(panelChildOpen.getAttribute('data-object-id') || '').trim();
        const campaignId = String(panelChildOpen.getAttribute('data-campaign-id') || '').trim();
        openObjectPanelChild(moduleType, objectId, campaignId).catch(err => {
          toast(`Unable to open child: ${String(err)}`, 'error');
        });
        return;
      }

      const menuAction = target.closest('[data-module-menu-action]');
      if (menuAction instanceof HTMLElement) {
        event.preventDefault();
        event.stopPropagation();
        const action = String(menuAction.getAttribute('data-module-menu-action') || '');
        const moduleType = String(menuAction.getAttribute('data-module-type') || '');
        const objectId = String(menuAction.getAttribute('data-object-id') || '');
        closeAllModuleOptionMenus();
        handleModuleMenuAction(action, moduleType, objectId, menuAction).catch(err => {
          toast(`Menu action failed: ${String(err)}`, 'error');
        });
        return;
      }

      const optionsTrigger = target.closest('[data-module-options-trigger]');
      if (optionsTrigger instanceof HTMLElement) {
        event.preventDefault();
        event.stopPropagation();
        const optionsWrap = optionsTrigger.closest('[data-options-wrap], [data-module-options], [data-list-options]');
        if (!(optionsWrap instanceof HTMLElement)) return;
        const opening = !optionsWrap.classList.contains('open');
        closeAllModuleOptionMenus(optionsWrap);
        optionsWrap.classList.toggle('open', opening);
        optionsTrigger.setAttribute('aria-expanded', opening ? 'true' : 'false');
        return;
      }

      const option = target.closest('[data-dropdown-option]');
      if (option) {
        event.preventDefault();
        event.stopPropagation();
        const dropdown = option.closest('.pill-dropdown');
        if (!dropdown) return;
        const kind = String(dropdown.getAttribute('data-dropdown-kind') || 'status').toLowerCase();
        const objectType = String(dropdown.getAttribute('data-object-type') || '').toLowerCase();
        const context = String(dropdown.getAttribute('data-context') || 'queue');
        const value = String(option.getAttribute('data-value') || '');
        if (context === 'panel') {
          applyPanelDropdownDraftSelection(option, dropdown);
          return;
        }
        if (kind === 'owner') {
          const initials = String(option.getAttribute('data-initials') || '--');
          const fullName = String(option.getAttribute('data-name') || '');
          const objectType = String(dropdown.getAttribute('data-object-type') || '').toLowerCase();
          const objectId = String(dropdown.getAttribute('data-object-id') || '');
          const roleKey = String(dropdown.getAttribute('data-role-key') || '').toLowerCase();
          if (objectType === 'step') {
            autoSaveStepOwnerFromDropdown(objectId, value, initials, fullName, context, dropdown);
            return;
          }
          if (objectType === 'deliverable') {
            autoSaveDeliverableOwnerFromDropdown(objectId, value, initials, fullName, context, dropdown);
            return;
          }
          if (objectType === 'campaign_assignment') {
            autoSaveCampaignAssignmentFromDropdown(objectId, roleKey, value, initials, fullName, dropdown);
            return;
          }
          updateOwnerSelectionFromDropdown(dropdown, value, initials, fullName);
          return;
        }
        const objectId = String(dropdown.getAttribute('data-object-id') || '');
        const raw = String(option.getAttribute('data-raw') || value);
        if (objectType === 'step') {
          autoSaveStepStatusFromDropdown(objectId, value, context, dropdown);
          return;
        }
        if (objectType === 'deliverable') {
          autoSaveDeliverableStatusFromDropdown(objectId, raw, value, dropdown);
          return;
        }
        if (objectType === 'campaign') {
          autoSaveCampaignStatusFromDropdown(objectId, value, dropdown);
          return;
        }
        return;
      }

      const trigger = target.closest('[data-dropdown-trigger]');
      if (trigger) {
        event.preventDefault();
        event.stopPropagation();
        const dropdown = trigger.closest('.pill-dropdown');
        if (!dropdown || trigger.hasAttribute('disabled')) return;
        if (dropdown.classList.contains('open')) {
          closeAllPillDropdowns();
        } else {
          openPillDropdown(dropdown);
        }
        return;
      }

      closeAllModuleOptionMenus();
      closeAllPillDropdowns();
    });

    document.addEventListener('keydown', (event) => {
      const key = event.key;
      if (key === 'Escape') {
        closeUsersDropdown();
        closeAllModuleOptionMenus();
        closeAllPillDropdowns();
        closeObjectPanel();
        return;
      }
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;

      const trigger = target.closest('[data-dropdown-trigger]');
      if (trigger && (key === 'Enter' || key === ' ' || key === 'ArrowDown')) {
        event.preventDefault();
        const dropdown = trigger.closest('.pill-dropdown');
        if (!dropdown || trigger.hasAttribute('disabled')) return;
        openPillDropdown(dropdown);
        return;
      }

      const option = target.closest('[data-dropdown-option]');
      if (!option) return;
      const menu = option.closest('.pill-dropdown-menu');
      if (!menu) return;
      const options = Array.from(menu.querySelectorAll('[data-dropdown-option]'));
      const idx = options.indexOf(option);
      if (idx < 0) return;
      if (key === 'ArrowDown') {
        event.preventDefault();
        options[(idx + 1) % options.length]?.focus();
      } else if (key === 'ArrowUp') {
        event.preventDefault();
        options[(idx - 1 + options.length) % options.length]?.focus();
      } else if (key === 'Enter' || key === ' ') {
        event.preventDefault();
        option.click();
      }
    });
    document.addEventListener('toggle', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (!target.classList.contains('module-card')) return;
      requestAnimationFrame(() => applyModuleLayoutRules());
    }, true);
    bootstrapApp().catch(err => log('Initial load failed', String(err)));
  </script>
</body>
</html>
"""
    return (
        html.replace("__NAV_CONTROLS__", _nav_controls_html())
        .replace("__UI_FLAGS__", json.dumps(ui_flags))
    )
