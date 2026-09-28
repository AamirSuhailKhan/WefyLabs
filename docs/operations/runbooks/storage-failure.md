# RUNBOOK — OBJECT STORAGE / S3 UPLOAD FAILURE
## Code: RB-STOR-010 | Severity: P2

---

## 1. Symptoms & Triggers
- Property brochure or media uploads fail with HTTP 502 / S3 AccessDenied / ConnectionTimeout.
- Signed URL generation throws expired or invalid credential exceptions.

## 2. Diagnostics
1. Test storage bucket reachability:
   ```bash
   aws s3 ls s3://$STORAGE_BUCKET_NAME/
   ```
2. Verify IAM role / AWS credentials in environment or Secrets Manager.

## 3. Mitigation & Recovery
- Re-authenticate or rotate AWS access keys if permission revoked.
- Buffer uploaded files temporarily to local SSD storage before background sync.
- Return graceful UI notification to user that media processing is deferred.
