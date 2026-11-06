# Dispatch scoring

The approved policy weights are retained exactly: technical expertise 35%,
current workload 25%, historical SLA success 15%, geographical proximity 15%,
real-time availability 5%, and estimated travel time 5%.

Unavailable engineers are excluded before scoring. Workload is min-max
normalised among eligible engineers, where lower workload is better. Expertise
is the fraction of requested skills the engineer holds, compared case
insensitively. A dispatch request may supply `required_skills`; if it supplies
only `incident_category`, that category is used as its one required skill.

Historical SLA success is the fraction of that engineer's recorded completed
assignments whose `sla_met` value is true. No completion records are created by
the system. If at least one eligible engineer has records, an engineer with no
history receives an explicit neutral 0.5 score; this represents unknown
evidence, not a successful outcome. If no eligible engineer has history, the
SLA factor is inactive.

Scores are the weighted average over the active factors only. Geographic
proximity is active only when the incident and at least one eligible engineer
have complete latitude/longitude pairs. It uses the Haversine formula to
calculate a straight-line distance in kilometres, then min-max normalises it
among engineers with usable coordinates (shorter distance is better). This is
not a road distance or an estimated travel time.

If an incident has no complete coordinate pair, proximity is inactive for all
engineers. If only some eligible engineers have coordinate evidence, proximity
is active and reported for those engineers only; candidates missing coordinates
receive no invented value, and their individual score is normalised over their
remaining supported criteria. The response identifies this with
`missing_engineer_coordinates` and its per-candidate active weight total.
Latitude must be between -90 and 90 and longitude between -180 and 180.
Coordinates are nullable and are persisted for engineer profiles and tickets,
so existing profiles and tickets remain valid without location evidence.

Estimated travel time remains inactive and is reported as a limitation because
the system has no routing or travel-time data.
