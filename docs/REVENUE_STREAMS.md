# Revenue streams beyond demand savings

Demand savings and ConnectedSolutions are modeled already (config/rates.yaml,
config/connected_solutions.yaml). This page checks four other streams for a
behind-the-meter battery block of 250 kW and 522 kWh, read on 2026-10-20. A
stream is modeled only when a sourced value and an eligibility rule can be
read; otherwise it is unmodeled, with what is missing.

| Stream | Modeled | Why |
|---|---|---|
| G-3 optional coincident peak transmission | No | Value and eligibility read, but the net value needs the ISO-NE monthly peak hours, not yet read |
| ISO-NE capacity payments | No | Price read, and co-participation with ConnectedSolutions is allowed; ISO-NE's own eligibility rules for one small behind-the-meter battery not read |
| Massachusetts clean peak credits | No | Co-participation with ConnectedSolutions is allowed; mass.gov blocks automated downloads, so neither the value nor the storage rules could be read |
| Investment tax credit | Yes, on the cost side | Rate and eligibility read; whether a given battery qualifies depends on its supply chain |
| Depreciation | No | Rules read; the value depends on the operator's tax rate and tax appetite |

## G-3 optional coincident peak transmission

What it pays: a National Grid G-3 customer may elect to pay transmission on
its 60-minute demand at the ISO New England monthly network peak, at $21.91
per kW-month, instead of $0.03455 per kWh on all its energy. It must stay on
the option for at least 12 consecutive months. A battery that discharges at
the monthly ISO-NE peak hour lowers that demand.

Eligibility: G-3 customers only (over 200 kW), by election. Eversource's
Greater Boston G-3 has a similar option at $22.39 per kW, but that schedule
is for primary voltage service, which the model does not assign.

Source: National Grid tariff M.D.P.U. No. 1591 (G-3), Optional Transmission
Coincident Peak Billing, and the Summary of Electric Delivery Service Rates
M.D.P.U. No. 1-26-I, effective 2026-10-01, sheet 3,
https://www.nationalgridus.com/media/pdfs/billing-payments/tariffs/mae/meco_delivery.pdf.

What a model would need: the hour of each monthly ISO-NE network peak for the
simulated weather year (2018), the building's load in that hour, and the
battery's state then, since the same energy also serves demand savings and
ConnectedSolutions events. The value is a switch: the site saves $0.03455 on
every kWh and pays $21.91 per kW of coincident demand, so it helps only
buildings whose load is low at the ISO-NE peak hour or can be made low.

## ISO-NE capacity payments

What it pays: resources that clear the Forward Capacity Auction are paid the
clearing price per kW-month for the commitment period. FCA 18 (June 2027 to
May 2028) cleared at $3.580 per kW-month in all zones; FCA 17 (2026/2027) at
$2.590. ISO-NE is moving to prompt or seasonal auctions held closer to
delivery; no forward auction has set a price after 2027/2028.

Source: ISO New England, Key Stats, Markets,
https://www.iso-ne.com/about/key-stats/markets, read 2026-10-20 (no page
date shown).

Eligibility: ISO-NE's own rules not read. A single 250 kW behind-the-meter
battery would take part through a demand response aggregator, under
ISO-NE's rules for demand capacity resources.

Stacking with ConnectedSolutions: allowed. The offering materials let
customers take part in ISO-NE demand resource programs and
ConnectedSolutions together, with two risks: a ConnectedSolutions event in
ISO-NE's 10-day baseline period can erode the customer's ISO-NE baseline,
and an earlier ConnectedSolutions event can lower ISO-NE's same-day
adjustment. Not allowed: any ISO-NE program that would reconstitute the
ConnectedSolutions curtailment into the installed capacity requirement
(ICR); the materials say the current Forward Capacity Market rarely does.
Source: Mass Save, Offering Materials for ConnectedSolutions for C&I Customers,
6/08/2023, https://www.masssave.com/-/media/Files/PDFs/Business/CI-ConnectedSolutions-Offering-Materials_June-2023.pdf, Co-Participation in ISO-NE Demand Resource Programs,
pages 15 to 16, read 2026-10-20.

What a model would need: the ISO-NE eligibility and qualification rules for
a behind-the-meter battery of this size, the rule on combining capacity
payments with ConnectedSolutions, and a price for commitment periods after
May 2028.

## Massachusetts clean peak credits

What it pays: Clean Peak Energy Certificates for energy delivered during
seasonal peak windows, priced per MWh, not per kW. Search summaries mention
an Alternative Compliance Payment of $45 or $65 per MWh and a May 28, 2026
emergency rulemaking that changed storage multipliers. None of this could be
checked.

Stacking with ConnectedSolutions: allowed. The offering materials say
customers may take part in the Clean Peak Standard and ConnectedSolutions,
and the program administrator reserves no rights to the clean peak
certificates. Source: the same offering materials, Co-Participation in the
Clean Peak Standard (CPS) Program, page 15, read 2026-10-20.

Eligibility: not read. Search summaries say a qualified storage system must
be charged from qualified renewable resources or during set windows, and
mention a minimum duration of four hours; the battery block holds a little
under two hours at full power. Unverified.

Source: mass.gov returns HTTP 403 to automated downloads. Documents to
download by hand: 225 CMR 21.00 as amended by the May 28, 2026 emergency
filing, DOER's Clean Peak Energy Standard guideline on Qualified Energy
Storage Systems, and DOER's notice of the current Alternative Compliance
Payment rate.

What a model would need: those three documents, then the seasonal peak
windows, the battery's discharge in them, and a certificate price.

## Investment tax credit

What it pays: a credit on the installed cost. The base rate is 6 percent;
energy storage technology with a capacity under 1 MW gets 30 percent without
the prevailing wage and apprenticeship requirements. Domestic content and
energy community adders of 10 points each are not modeled.

Eligibility: energy storage technology of at least 5 kWh placed in service
after 2024. No credit if construction began after December 31, 2025 and
includes material assistance from a prohibited foreign entity, or if the
taxpayer is a specified foreign entity. The FEOC rules therefore decide
whether a given battery qualifies.

Sources: 26 U.S.C. 48E(a)(2)(B)(ii)(I), (c)(3) and (d)(6), as amended by
Pub. L. 119-21, and 48(c)(6)(A)(i), https://www.law.cornell.edu/uscode/text/26/48E
and https://www.law.cornell.edu/uscode/text/26/48; IRS, Clean Electricity
Investment Credit, https://www.irs.gov/credits-deductions/clean-electricity-investment-credit
(updated 2026-01-05). All read 2026-10-20.

Model: a cost-side toggle that lowers the installed cost by the credit,
used only in the break-even column and the optional model confidence, off
by default (config/costs.yaml). It is not a revenue stream.

## Eversource metering for ConnectedSolutions

Not a revenue stream but an unmodeled cost on the ConnectedSolutions
stream for Eversource sites (the 34 in Canton and Sharon). All Eversource
customers in the program must install metering that sends real-time
interval data to Eversource, with the battery measured at the asset level.
Customers may apply for an incentive of up to $1,500 per meter toward the
metering cost. Source: Mass Save, Offering Materials for ConnectedSolutions for C&I Customers,
6/08/2023, https://www.masssave.com/-/media/Files/PDFs/Business/CI-ConnectedSolutions-Offering-Materials_June-2023.pdf, Customer Interval Data, For
Eversource Customers, page 15, read 2026-10-20.

What a model would need: the metering cost per site, net of the incentive.
Neither the cost nor the number of meters per site is known, so it is not
modeled.

## Depreciation

What it pays: a tax deduction for the battery's owner. Energy storage
technology is 5-year property, and property acquired after January 19, 2025
qualifies for a bonus allowance of 100 percent of the adjusted basis in the
first year. The depreciable basis is reduced by half the ITC.

Sources: 26 U.S.C. 168(e)(3)(B)(viii) and 168(k)(1)(A), with the effective
date of Pub. L. 119-21 section 70301, and 26 U.S.C. 50(c)(3),
https://www.law.cornell.edu/uscode/text/26/168 and
https://www.law.cornell.edu/uscode/text/26/50, read 2026-10-20.

What a model would need: the operator's marginal tax rate and whether it can
use the deduction in the first year (tax appetite). Neither is public.

Nothing on this page is tax advice; the operator's tax position decides what
the ITC and depreciation are worth.
