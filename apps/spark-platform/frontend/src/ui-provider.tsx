import { LinkProvider, Theme } from "@astryxdesign/core";
import { neutralTheme } from "@astryxdesign/theme-neutral/built";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { Link as RouterLink } from "react-router-dom";

function ApplicationLink({
  href = "/",
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <RouterLink to={href} {...props} />;
}

export function UIProvider({ children }: { children: ReactNode }) {
  return (
    <Theme theme={neutralTheme} mode="light">
      <LinkProvider component={ApplicationLink}>{children}</LinkProvider>
    </Theme>
  );
}
