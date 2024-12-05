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
  IconButton,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
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

interface Secret {
  id: string
  name: string
  value: string
  created_at: string
  updated_at: string
}

interface TabPanelProps {
  children?: React.ReactNode
  index: number
  value: number
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  )
}

export function OrganizationDetail() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const [organization, setOrganization] = useState<Organization | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [secrets, setSecrets] = useState<Secret[]>([])
  const [isAdmin, setIsAdmin] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [openInviteDialog, setOpenInviteDialog] = useState(false)
  const [openEditDialog, setOpenEditDialog] = useState(false)
  const [openSecretDialog, setOpenSecretDialog] = useState(false)
  const [editName, setEditName] = useState('')
  const [secretName, setSecretName] = useState('')
  const [secretValue, setSecretValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [tabValue, setTabValue] = useState(0)

  useEffect(() => {
    if (id) {
      fetchOrganizationData()
    }
  }, [id])

  async function fetchOrganizationData() {
    try {
      // Fetch organization details
      const { data: org, error: orgError } = await supabase
        .from('organizations')
        .select('*')
        .eq('id', id)
        .single()

      if (orgError) throw orgError
      setOrganization(org)
      setEditName(org.name)

      // Fetch members
      const { data: memberData, error: memberError } = await supabase
        .rpc('get_organization_members', { org_id: id })

      if (memberError) throw memberError

      // Check if current user is admin
      const currentUserMember = memberData.find((m: { user_id: string }) => m.user_id === user?.id)
      setIsAdmin(currentUserMember?.role === 'admin')

      setMembers(memberData.map((m: { user_id: string, role: string }) => ({
        user_id: m.user_id,
        email: m.email,
        role: m.role
      })))

      // Fetch secrets if admin
      if (currentUserMember?.role === 'admin') {
        const { data: secretData, error: secretError } = await supabase
          .from('organization_secrets')
          .select('*')
          .eq('organization_id', id)

        if (secretError) throw secretError
        setSecrets(secretData)
      }
    } catch (err) {
      console.error('Error fetching data:', err)
      setError(err instanceof Error ? err.message : 'An error occurred')
    }
  }

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

  const handleRemoveMember = async (userId: string) => {
    try {
      const { error } = await supabase
        .rpc('remove_organization_member', {
          org_id: id,
          member_id: userId
        })

      if (error) throw error

      setMembers(members.filter(member => member.user_id !== userId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove member')
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
      setError(err instanceof Error ? err.message : 'Failed to send invitation')
    }
  }

  const handleUpdateOrganization = async () => {
    try {
      const { error } = await supabase
        .rpc('update_organization', {
          org_id: id,
          new_name: editName
        })

      if (error) throw error

      setOrganization(prev => prev ? { ...prev, name: editName } : null)
      setOpenEditDialog(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update organization')
    }
  }

  const handleManageSecret = async () => {
    try {
      const { error } = await supabase
        .rpc('manage_organization_secret', {
          org_id: id,
          secret_name: secretName,
          secret_value: secretValue
        })

      if (error) throw error

      // Refresh secrets
      const { data: secretData, error: secretError } = await supabase
        .from('organization_secrets')
        .select('*')
        .eq('organization_id', id)

      if (secretError) throw secretError
      setSecrets(secretData)

      setSecretName('')
      setSecretValue('')
      setOpenSecretDialog(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to manage secret')
    }
  }

  const handleDeleteSecret = async (name: string) => {
    try {
      const { error } = await supabase
        .rpc('delete_organization_secret', {
          org_id: id,
          secret_name: name
        })

      if (error) throw error

      setSecrets(secrets.filter(s => s.name !== name))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete secret')
    }
  }

  if (error) return <Typography color="error">{error}</Typography>
  if (!organization) return <Typography>Loading...</Typography>

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">
          {organization.name}
        </Typography>
        {isAdmin && (
          <IconButton onClick={() => setOpenEditDialog(true)}>
            <EditIcon />
          </IconButton>
        )}
      </Box>

      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
          <Tab label="Members" />
          {isAdmin && <Tab label="Secrets" />}
        </Tabs>
      </Box>

      <TabPanel value={tabValue} index={0}>
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
              <ListItemText 
                primary={member.email}
                secondary={member.user_id === user?.id ? '(You)' : null}
              />
              <Box display="flex" alignItems="center" gap={2}>
                {isAdmin && member.user_id !== user?.id && (
                  <FormControl variant="outlined" size="small">
                    <Select
                      value={member.role}
                      onChange={(e) => handleRoleChange(member.user_id, e.target.value as 'admin' | 'user')}
                    >
                      <MenuItem value="user">User</MenuItem>
                      <MenuItem value="admin">Admin</MenuItem>
                    </Select>
                  </FormControl>
                )}
                {!isAdmin && (
                  <Typography variant="body2" color="textSecondary">
                    {member.role}
                  </Typography>
                )}
                {isAdmin && member.user_id !== user?.id && (
                  <IconButton 
                    edge="end" 
                    onClick={() => handleRemoveMember(member.user_id)}
                    color="error"
                  >
                    <DeleteIcon />
                  </IconButton>
                )}
              </Box>
            </ListItem>
          ))}
        </List>
      </TabPanel>

      {isAdmin && (
        <TabPanel value={tabValue} index={1}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">Secrets</Typography>
            <Button
              variant="contained"
              color="primary"
              onClick={() => setOpenSecretDialog(true)}
            >
              Add Secret
            </Button>
          </Box>

          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Last Updated</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {secrets.map((secret) => (
                  <TableRow key={secret.id}>
                    <TableCell>{secret.name}</TableCell>
                    <TableCell>
                      {new Date(secret.updated_at).toLocaleString()}
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        onClick={() => handleDeleteSecret(secret.name)}
                        color="error"
                      >
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>
      )}

      {/* Invite Dialog */}
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
          <Button 
            onClick={handleInvite}
            variant="contained"
            color="primary"
            disabled={!inviteEmail}
          >
            Send Invitation
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit Organization Dialog */}
      <Dialog open={openEditDialog} onClose={() => setOpenEditDialog(false)}>
        <DialogTitle>Edit Organization</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Organization Name"
            type="text"
            fullWidth
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenEditDialog(false)}>Cancel</Button>
          <Button 
            onClick={handleUpdateOrganization}
            variant="contained"
            color="primary"
            disabled={!editName || editName === organization.name}
          >
            Update
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add Secret Dialog */}
      <Dialog open={openSecretDialog} onClose={() => setOpenSecretDialog(false)}>
        <DialogTitle>Add Secret</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Secret Name"
            type="text"
            fullWidth
            value={secretName}
            onChange={(e) => setSecretName(e.target.value)}
          />
          <TextField
            margin="dense"
            label="Secret Value"
            type="password"
            fullWidth
            value={secretValue}
            onChange={(e) => setSecretValue(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenSecretDialog(false)}>Cancel</Button>
          <Button 
            onClick={handleManageSecret}
            variant="contained"
            color="primary"
            disabled={!secretName || !secretValue}
          >
            Save Secret
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}