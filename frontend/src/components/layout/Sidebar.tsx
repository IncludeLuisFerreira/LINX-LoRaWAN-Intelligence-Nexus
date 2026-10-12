import { NavLink } from 'react-router-dom';
import { cn } from '../../utils/cn';
import { Building, Cpu, Device } from '../ui/icons';

const navItems = [
  { label: 'Tenants', path: '/tenants', icon: Building },
  { label: 'Devices', path: '/devices', icon: Device },
  { label: 'Onboarding', path: '/onboarding', icon: Cpu },
];

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
      isActive
        ? 'bg-primary-50 text-primary-700'
        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
    );

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-20 bg-slate-900/40 md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-border bg-surface transition-transform duration-300 ease-in-out md:static md:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-16 items-center gap-2 border-b border-border px-5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-500 text-sm font-bold text-white">
            Lx
          </span>
          <span className="text-lg font-bold tracking-wide text-slate-800">
            LINX
          </span>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={linkClass}
              onClick={onClose}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  );
}
