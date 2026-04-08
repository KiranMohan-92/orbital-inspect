{{/*
Expand the name of the chart.
*/}}
{{- define "orbital-inspect.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "orbital-inspect.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart label.
*/}}
{{- define "orbital-inspect.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources.
*/}}
{{- define "orbital-inspect.labels" -}}
helm.sh/chart: {{ include "orbital-inspect.chart" . }}
{{ include "orbital-inspect.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "orbital-inspect.selectorLabels" -}}
app.kubernetes.io/name: {{ include "orbital-inspect.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
API-specific selector labels.
*/}}
{{- define "orbital-inspect.apiSelectorLabels" -}}
{{ include "orbital-inspect.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Worker-specific selector labels.
*/}}
{{- define "orbital-inspect.workerSelectorLabels" -}}
{{ include "orbital-inspect.selectorLabels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Frontend-specific selector labels.
*/}}
{{- define "orbital-inspect.frontendSelectorLabels" -}}
{{ include "orbital-inspect.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Service account name.
*/}}
{{- define "orbital-inspect.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "orbital-inspect.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Shared envFrom block: ConfigMap + all external secrets.
Used by both api and worker deployments.
*/}}
{{- define "orbital-inspect.envFrom" -}}
- configMapRef:
    name: {{ include "orbital-inspect.fullname" . }}-config
- secretRef:
    name: {{ .Values.auth.existingSecret }}
- secretRef:
    name: {{ .Values.postgresql.existingSecret }}
- secretRef:
    name: {{ .Values.redis.existingSecret }}
- secretRef:
    name: {{ .Values.storage.existingSecret }}
- secretRef:
    name: {{ .Values.gemini.existingSecret }}
{{- if .Values.spaceTrack.existingSecret }}
- secretRef:
    name: {{ .Values.spaceTrack.existingSecret }}
{{- end }}
{{- end }}
