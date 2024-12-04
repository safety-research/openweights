import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Box,
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemText,
  Chip,
} from '@mui/material'
import { supabase } from '../../supabaseClient'

interface Organization {
  id: string
  name: string
  role: 'admin' | 'user'
}

export function OrganizationsList() {
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchOrganizations() {
      try {
        const { data: memberships, error: membershipError } = await supabase
          .from('organization_members')
          .select(`
            organization_id,
            role,
            organizations (
              id,
              name
            )
          `)
          .throwOnError()

        if (membershipError) throw membershipError

        const orgs = memberships.map(membership => ({
          id: membership.organizations.id,
          name: membership.organizations.name,
          role: membership.role
        }))

        setOrganizations(orgs)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch organizations')
      } finally {
        setLoading(false)
      }
    }

    fetchOrganizations()
  }, [])

  if (loading) return <Typography>Loading...</Typography>
  if (error) return <Typography color="error">{error}</Typography>

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Your Organizations
      </Typography>
      <List>
        {organizations.map((org) => (
          <ListItem key={org.id} component={Card} sx={{ mb: 2 }}>
            <CardContent sx={{ width: '100%' }}>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography variant="h6" component={Link} to={`/organizations/${org.id}`}>
                    {org.name}
                  </Typography>
                  <Typography color="textSecondary" variant="body2">
                    ID: {org.id}
                  </Typography>
                </Box>
                <Chip
                  label={org.role}
                  color={org.role === 'admin' ? 'primary' : 'default'}
                />
              </Box>
            </CardContent>
          </ListItem>
        ))}
      </List>
    </Box>
  )
}