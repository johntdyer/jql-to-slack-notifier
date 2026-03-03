{{/*
Expand the name of the chart.
*/}}
{{- define "jql-to-slack-notifier.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "jql-to-slack-notifier.fullname" -}}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "jql-to-slack-notifier.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "jql-to-slack-notifier.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "jql-to-slack-notifier.selectorLabels" -}}
app.kubernetes.io/name: {{ include "jql-to-slack-notifier.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
The image tag — use .Values.image.tag if set, otherwise fall back to appVersion.
*/}}
{{- define "jql-to-slack-notifier.imageTag" -}}
{{- .Values.image.tag | default .Chart.AppVersion }}
{{- end }}

{{/*
Secret name — use existingSecret if provided, otherwise the fullname of this release.
*/}}
{{- define "jql-to-slack-notifier.secretName" -}}
{{- .Values.existingSecret | default (include "jql-to-slack-notifier.fullname" .) }}
{{- end }}
