import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-3xl px-5 py-24">
      <EmptyState title="Page not found">
        The page you were looking for does not exist. <Link to="/" className="text-teal underline">Return home</Link>.
      </EmptyState>
    </div>
  );
}
