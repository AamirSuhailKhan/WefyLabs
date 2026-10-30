with open('docs/audits/PHASE14_FINAL_TRANSFORMATION_EXECUTIVE_REPORT.md', 'r', encoding='utf-8') as f:
    c = f.read()

target = """     - Under **Section 8(9)**, WefyLabs is required to publish the contact details of a **Data Grievance Officer** to handle data principal inquiries and redressal within statutory timelines.
   - **Cross-Border Data Transfers:** Governed by **Section 16(1)**. Transfers are broadly permitted to foreign jurisdictions *unless* explicitly restricted by a notified "negative list".
   - **Status:** `EXTERNAL LEGAL REVIEW REQUIRED` to finalize Data Grievance Officer appointment, privacy notice templates, and consent manager integration before General Availability."""

replacement = """     - Under **Section 8(9)**, a Data Fiduciary must establish an effective grievance redressal mechanism and publish the business contact information of the Data Protection Officer (if designated) or an authorized officer/individual who is able to answer on behalf of the Data Fiduciary regarding the processing of personal data (frequently designated operationally as a Grievance Officer, though the statute itself specifies an authorized contact person rather than a mandatory formal title).
   - **Cross-Border Data Transfers:** Governed by **Section 16(1)**. Transfers are broadly permitted to foreign jurisdictions *unless* explicitly restricted by a notified "negative list".
   - **Status:** `EXTERNAL LEGAL REVIEW REQUIRED` to finalize grievance contact publication, privacy notice templates, and consent manager integration before General Availability. Substantive fiduciary obligations and enforcement by the Data Protection Board of India (DPBI) remain subject to the phased commencement schedule notified by MeitY under Section 1(2)."""

c_norm = c.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
replacement_norm = replacement.replace('\r\n', '\n')

if target_norm in c_norm:
    c_norm = c_norm.replace(target_norm, replacement_norm, 1)
    c_final = c_norm.replace('\n', '\r\n')
    with open('docs/audits/PHASE14_FINAL_TRANSFORMATION_EXECUTIVE_REPORT.md', 'w', encoding='utf-8', newline='') as f:
        f.write(c_final)
    print("SUCCESS")
else:
    print("FAILED: target_norm not in c_norm")

