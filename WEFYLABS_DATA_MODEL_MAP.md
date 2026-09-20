# WEFYLABS DATA MODEL MAP

| Domain | Models (representative) | Migration/API/UI evidence | Reality |
|---|---|---|---|
| Organization/auth | Organization, OrganizationMember, User, Broker, invitations | code/routes; tests selected | PARTIAL tenant proof |
| Lead/CRM | Lead, Contact, Activity, Task, Meeting, Note, Tag, PipelineStage | code/routes/UI | VERIFIED IN CODE |
| Acquisition | LeadSource, Campaign, AcquisitionEvent, Attribution, Prospect | code/routes/UI | PARTIALLY IMPLEMENTED |
| Identity | identity models + resolution module | code and selected tests | TEST VERIFIED only for selected cases |
| Property | PropertyListing, Media, PriceHistory, LeadPropertyInterest | code/routes/UI | flat listing, not graph |
| Matching | BuyerProfile/Preference/Constraint, Recommendation* | code/tests | canonical engine unproven |
| Conversations | Conversation; Unified*/Omnichannel*/ChannelMessage; Copilot*/Agent* | code/UI | duplicated ownership |
| Qualification | QualificationFact/Conflict/Policy/Snapshot | code/tests | structured path exists |
| Follow-up | FollowUpPolicy/Sequence/Enrollment/Execution/Decision | code/UI/workers | runtime unverified |
| Calendar | accounts, meetings, holds, events, viewings, outcomes | code | provider unverified |
| Revenue | RevenueOpportunity, FeedbackLog, ActionExecution | code/tests/UI | test-proven selected paths |
| Knowledge/memory | Knowledge*, Memory* | code/workers | storage/retrieval runtime unknown |

## Required Model Decisions

1. Store real `organization_id` on every tenant-owned entity; remove aliases as tenancy authority.
2. Make property/project/building/unit relationships explicit only when inventory source requires them; do not fabricate a graph.
3. Select a canonical conversation envelope, then adapt legacy/Copilot/agent views.
4. Separate matching score from revenue opportunity score and retain inputs/explanations/audit.
