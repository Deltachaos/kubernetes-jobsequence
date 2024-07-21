# kubernetes-jobsequence
A Kubernetes Job that spawns Jobs in a sequence, and waits for there completion

# Example

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: job-serviceaccount
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: job-cluster-admin-binding
subjects:
- kind: ServiceAccount
  name: job-serviceaccount
  namespace: default
roleRef:
  kind: ClusterRole
  name: cluster-admin
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: do-subjobs
  namespace: default
data:
  job1.yaml: |
    template:
      spec:
        containers:
          - name: sleep-container
            image: busybox
            command: ["sleep", "10"]
          restartPolicy: Never
  job2.yaml: |
    template:
      spec:
        containers:
          - name: sleep-container
            image: busybox
            command: ["sleep", "20"]
          restartPolicy: Never
---
apiVersion: batch/v1
kind: Job
metadata:
  name: do-something
  namespace: default
spec:
  template:
    spec:
      serviceAccountName: job-serviceaccount
      volumes:
        - name: jobs
          configMap:
            name: do-subjobs
      containers:
        - name: runner
          image: ghcr.io/deltachaos/kubernetes-jobsequence
          volumeMounts:
            - name: jobs
              mountPath: /jobs
      restartPolicy: Never
```
