import { HashRouter, Routes, Route, NavLink } from "react-router-dom";
import ShoppingPage from "./pages/ShoppingPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import OrderDetailPage from "./pages/OrderDetailPage.jsx";

function TopNav() {
  const linkClass = ({ isActive }) =>
    `px-4 py-2 rounded-full text-sm font-medium transition-colors ${
      isActive ? "bg-signal text-ink" : "text-muted hover:text-paper"
    }`;

  return (
    <header className="border-b border-line px-6 py-4 flex items-center justify-between sticky top-0 bg-ink/95 backdrop-blur z-20">
      <div className="flex items-baseline gap-2">
        <span className="font-display text-xl tracking-tight">PayPilot AI</span>
        <span className="text-xs text-muted hidden sm:inline">
          bounded agentic checkout · Razorpay test mode
        </span>
      </div>
      <nav className="flex gap-2">
        <NavLink to="/" end className={linkClass}>
          Shop
        </NavLink>
        <NavLink to="/dashboard" className={linkClass}>
          Merchant Dashboard
        </NavLink>
      </nav>
    </header>
  );
}

export default function App() {
  return (
    <HashRouter>
      <div className="min-h-screen flex flex-col">
        <TopNav />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<ShoppingPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/orders/:orderId" element={<OrderDetailPage />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}
