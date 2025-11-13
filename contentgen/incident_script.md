# Production API Gateway Outage - Nov 6, 2025

## Incident Script
Zoom: Warren-SRE: Everyone can hear me? Okay, we have OOM kills on the new deployment
Zoom: Preetha-Dev: I'm looking at the graphs now - every v3.2.1 instance has linear memory growth
Zoom: Warren-SRE: Declaring SEV-2. Marcus, you're incident commander. I'm rolling back now
Zoom: Deepank-Oncall: Copy that. I've got IC. Who's handling comms?
Zoom: Warren-SRE: We'll let ICOM handle comms so we can focus on resolving the problem
Zoom: Deepank-Oncall: We're seeing about 15% error rate right now. Warren's rolling back, should stabilize in 10-15
Zoom: Warren-SRE: Rollback is working - memory dropping back to normal levels
Zoom: Preetha-Dev: Looking through the changes now. There's not much in this release...
Zoom: Preetha-Dev: Got it! The new auth middleware isn't closing HTTP connections to auth-service
Zoom: Preetha-Dev: It's creating a new HTTP client for every auth-service validation without cleaning up. Classic connection leak
Zoom: Warren-SRE: Makes sense - that's why memory kept climbing. Connections never released
Zoom: Warren-SRE: Metrics look stable but let's watch for another 10 minutes before closing
Zoom: Deepank-Oncall: Agreed. Thanks everyone. Great response. Let's close it out
Zoom: Warren-SRE: Marking as resolved. Incident response complete.
