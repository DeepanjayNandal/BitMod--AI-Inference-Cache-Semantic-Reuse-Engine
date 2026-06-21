{{/*
Expand the name of the chart.
*/}}
{{- define "bitmod.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "bitmod.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "bitmod.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "bitmod.labels" -}}
helm.sh/chart: {{ include "bitmod.chart" . }}
{{ include "bitmod.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "bitmod.selectorLabels" -}}
app.kubernetes.io/name: {{ include "bitmod.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Gateway selector labels
*/}}
{{- define "bitmod.gateway.selectorLabels" -}}
{{ include "bitmod.selectorLabels" . }}
app.kubernetes.io/component: gateway
{{- end }}

{{/*
Chat selector labels
*/}}
{{- define "bitmod.chat.selectorLabels" -}}
{{ include "bitmod.selectorLabels" . }}
app.kubernetes.io/component: chat
{{- end }}

{{/*
Service account name
*/}}
{{- define "bitmod.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "bitmod.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Secret name for LLM API keys
*/}}
{{- define "bitmod.llmSecretName" -}}
{{- if .Values.llm.existingSecret }}
{{- .Values.llm.existingSecret }}
{{- else }}
{{- include "bitmod.fullname" . }}-llm
{{- end }}
{{- end }}

{{/*
Secret name for database credentials
*/}}
{{- define "bitmod.dbSecretName" -}}
{{- if .Values.database.postgresql.existingSecret }}
{{- .Values.database.postgresql.existingSecret }}
{{- else }}
{{- include "bitmod.fullname" . }}-db
{{- end }}
{{- end }}

{{/*
Secret name for auth
*/}}
{{- define "bitmod.authSecretName" -}}
{{- include "bitmod.fullname" . }}-auth
{{- end }}
