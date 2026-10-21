# ma-battery-prospecting

Ranks Massachusetts commercial and industrial sites by value per battery
block: the simulated yearly demand savings plus grid program revenue one
standard behind-the-meter battery block could bring, gross, before any host
share, using public data only. Cost and profit are not modeled: the operator
applies its own installed cost and host share.

Work in progress. Nothing here is ready to use yet.

## The report

report.html is one self-contained page, built from the committed export with
`make report` (no database needed). It is never committed: the owner attaches
the built file to each GitHub release, starting with v0.7.0. Open it by double
click; it makes no network requests.

The report can read an optional customer status file that you pick in the
browser: a CSV with the columns owner, address, town (optional) and status
(customer, contacted or declined). It is read locally and never uploaded. A row
matches a site by owner name or address, compared in upper case with
punctuation removed, owner names also without company words such as INC or LLC
and addresses with street words abbreviated (STREET to ST); a town, if given,
must match too. Matching sites get a status tag and are
hidden by default. See docs/customer_status.example.csv for the format, with
made-up rows. Real status files (customer_status*.csv) are gitignored and must
never be committed.
