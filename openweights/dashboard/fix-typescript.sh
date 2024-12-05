#!/bin/bash

# Fix AllView.tsx
sed -i 's/event: unknown/\_: unknown/' src/components/AllView.tsx

# Fix DetailViews.tsx
sed -i '/const hasFiles/d' src/components/DetailViews.tsx

# Fix JobsView.tsx
sed -i 's/\[\[key, value\]\]/[[_, value]]/' src/components/JobsView.tsx

# Fix OrganizationDetail.tsx
sed -i '/ListItemSecondaryAction,/d' src/components/Organizations/OrganizationDetail.tsx
sed -i 's/find(m =>/find((m: { user_id: string }) =>/' src/components/Organizations/OrganizationDetail.tsx
sed -i 's/map(m =>/map((m: { user_id: string, role: string }) =>/' src/components/Organizations/OrganizationDetail.tsx

# Fix OrganizationsList.tsx
sed -i 's/const { data, error }/const { error }/' src/components/Organizations/OrganizationsList.tsx