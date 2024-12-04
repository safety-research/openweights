import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material'
import { supabase } from '../../supabaseClient'
import { useAuth } from '../../contexts/AuthContext'

interface Member {
  user_id: string
  email: string
  role: 'admin' | 'user'
}

interface Organization {
  id: string
  name: string
}

export function OrganizationDetail() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const [organization, setOrganization] = useState<Organization | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [isAdmin, setIsAdmin] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [openInviteDialog, setOpenInviteDialog] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchOrganizationAndMembers() {
      try {
        // Fetch organization details
        const { data: org, error: orgError } = await supabase
          .from('organizations')
          .select('*')
          .eq('id', id)
          .single()

        if (orgError) throw orgError
        setOrganization(org)

        // Fetch members using a raw query to join with auth.users
        const { data: memberData, error: memberError } = await supabase
          .rpc('get_organization_members', { org_id: id })

        if (memberError) throw memberError

        // Check if current user is admin
        const currentUserMember = memberData.find(m => m.user_id === user?.id)
        setIsAdmin(currentUserMember?.role === 'admin')

        // Transform member data
        const transformedMembers = memberData.map(m => ({
          user_id: m.user_id,
          email: m.email,
          role: m.role
        }))

        setMembers(transformedMembers)
      } catch (err) {
        console.error('Error fetching data:', err)
        setError(err instanceof Error ? err.message : 'An error occurred')
      }
    }

    if (id) {
      fetchOrganizationAndMembers()
    }
  }, [id, user?.id])

  const handleRoleChange = async (userId: string, newRole: 'admin' | 'user') => {
    try {
      const { error } = await supabase
        .from('organization_members')
        .update({ role: newRole })
        .eq('organization_id', id)
        .eq('user_id', userId)

      if (error) throw error

      setMembers(members.map(member =>
        member.user_id === userId ? { ...member, role: newRole } : member
      ))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update role')
    }
  }

  const handleInvite = async () => {
    try {
      const { data, error } = await supabase
        .rpc('invite_organization_member', {
          org_id: id,
          member_email: inviteEmail,
          member_role: 'user'
        })

      if (error) throw error

      // Add the new member to the local state
      if (data) {
        setMembers([...members, {
          user_id: data.user_id,
          email: data.email,
          role: data.role
        }])
      }

      setInviteEmail('')
      setOpenInviteDialog(false)
    } catch (err) {
      console.error('Error inviting member:', err)
      setError(err instanceof Error ? err.message : 'Failed to send invitation')
    }
  }

  if (error) return <Typography color="error">{error}</Typography>
  if (!organization) return <Typography>Loading...</Typography>

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {organization.name}
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">Members</Typography>
          {isAdmin && (
            <Button
              variant="contained"
              color="primary"
              onClick={() => setOpenInviteDialog(true)}
            >
              Invite Member
            </Button>
          )}
        </Box>

        <List>
          {members.map((member) => (
            <ListItem key={member.user_id} divider>
              <ListItemText primary={member.email} />
              {isAdmin && member.user_id !== user?.id ? (
                <FormControl variant="outlined" size="small">
                  <Select
                    value={member.role}
                    onChange={(e) => handleRoleChange(member.user_id, e.target.value as 'admin' | 'user')}
                  >
                    <MenuItem value="user">User</MenuItem>
                    <MenuItem value="admin">Admin</MenuItem>
                  </Select>
                </FormControl>
              ) : (
                <Typography variant="body2" color="textSecondary">
                  {member.role}
                </Typography>
              )}
            </ListItem>
          ))}
        </List>
      </Paper>

      <Dialog open={openInviteDialog} onClose={() => setOpenInviteDialog(false)}>
        <DialogTitle>Invite New Member</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Email Address"
            type="email"
            fullWidth
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenInviteDialog(false)}>Cancel</Button>
          <Button onClick={handleInvite} variant="contained" color="primary">
            Send Invitation
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}