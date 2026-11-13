import React, { useState } from 'react'
import { Info, MoreHorizontal, Plus } from 'lucide-react'
import { Card, PageHeader, Pill, Tabs } from '../components/ui'

// shortcut: demo data only. There is no users/roles service yet (Keycloak per docs/04_architecture.md);
// replace with the identity API when it exists.
export const DEMO_USERS = [
  { name: 'Asha Kulkarni', email: 'asha.kulkarni@example.com', role: 'Admin', active: true },
  { name: 'Rahul Deshmukh', email: 'rahul.deshmukh@example.com', role: 'Maintenance engineer', active: true },
  { name: 'Meera Joshi', email: 'meera.joshi@example.com', role: 'Reliability engineer', active: true },
  { name: 'Vikram Patil', email: 'vikram.patil@example.com', role: 'Operator', active: true },
  { name: 'Sneha Rao', email: 'sneha.rao@example.com', role: 'Viewer', active: false },
]

const ROLES = [
  { name: 'Admin', can: 'Everything, including users, connectors and alarm rules.' },
  { name: 'Maintenance engineer', can: 'Create and close work orders, acknowledge alarms, edit PM plans.' },
  { name: 'Reliability engineer', can: 'Analytics, alarm rules and what-if simulations; read-only work orders.' },
  { name: 'Operator', can: 'View the plant and acknowledge alarms on their line.' },
  { name: 'Viewer', can: 'Read-only access to dashboards and the 3D plant.' },
]

const initials = (n: string) =>
  n
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)

export const UsersPage: React.FC = () => {
  const [tab, setTab] = useState<'users' | 'roles'>('users')
  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Users & Roles"
        sub="Who can use TwinOps and what each role may do."
        right={
          <button
            disabled
            title="Needs the user service (not built yet)"
            className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600/50 text-white text-sm font-semibold px-4 py-2 cursor-not-allowed"
          >
            <Plus className="w-4 h-4" /> Add user
          </button>
        }
      />
      <div className="flex items-start gap-2 rounded-xl bg-amber-50 ring-1 ring-amber-200 px-4 py-3 text-sm text-amber-800" role="note" data-testid="demo-banner">
        <Info className="w-4 h-4 mt-0.5 shrink-0" />
        <span>
          <strong>Demo data.</strong> TwinOps has no user service yet, so these users are examples and nothing here is saved.
          Login and roles will come from the identity service (Keycloak).
        </span>
      </div>
      <Card>
        <div className="px-5 pt-4">
          <Tabs
            tabs={[
              { id: 'users' as const, label: `Users (${DEMO_USERS.length})` },
              { id: 'roles' as const, label: `Roles (${ROLES.length})` },
            ]}
            active={tab}
            onChange={setTab}
          />
        </div>
        {tab === 'users' ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-slate-500">
                <tr className="text-left border-b border-slate-100">
                  <th className="px-5 py-2.5 font-medium">Name</th>
                  <th className="px-3 py-2.5 font-medium">Email</th>
                  <th className="px-3 py-2.5 font-medium">Role</th>
                  <th className="px-3 py-2.5 font-medium">Status</th>
                  <th className="px-5 py-2.5 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {DEMO_USERS.map((u) => (
                  <tr key={u.email}>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <span className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center">
                          {initials(u.name)}
                        </span>
                        <span className="font-medium text-slate-900">{u.name}</span>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-slate-600">{u.email}</td>
                    <td className="px-3 py-3">
                      <Pill tone="blue">{u.role}</Pill>
                    </td>
                    <td className="px-3 py-3">
                      <Pill tone={u.active ? 'green' : 'grey'}>{u.active ? 'Active' : 'Inactive'}</Pill>
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button disabled aria-label={`Actions for ${u.name} (not available yet)`} className="p-1 rounded text-slate-300 cursor-not-allowed">
                        <MoreHorizontal className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {ROLES.map((r) => (
              <li key={r.name} className="px-5 py-3 text-sm">
                <div className="font-medium text-slate-900">{r.name}</div>
                <div className="text-slate-500">{r.can}</div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
