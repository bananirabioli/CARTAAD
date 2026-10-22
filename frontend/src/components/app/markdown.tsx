import { Fragment } from "react";

/** Minimal markdown renderer for briefs and reports: headings, bullet lists, bold, paragraphs. */
function inline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <Fragment key={i}>{p}</Fragment>));
}

export function Markdown({ source }: { source: string }) {
  const blocks: React.ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="my-1 list-disc space-y-0.5 pl-5">
          {list.map((li, i) => (
            <li key={i}>{inline(li)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  for (const raw of source.split("\n")) {
    const line = raw.trimEnd();
    if (/^\s*[-*] /.test(line)) {
      list.push(line.replace(/^\s*[-*] /, ""));
      continue;
    }
    flush();
    if (!line.trim()) continue;
    const h = /^(#{1,4}) (.*)$/.exec(line);
    if (h) {
      const level = h[1].length;
      const cls = level <= 2 ? "mt-3 text-sm font-semibold" : "mt-2 text-sm font-medium";
      blocks.push(
        <p key={`h-${blocks.length}`} className={cls}>
          {inline(h[2])}
        </p>,
      );
    } else {
      blocks.push(
        <p key={`p-${blocks.length}`} className="my-1">
          {inline(line)}
        </p>,
      );
    }
  }
  flush();
  return <div className="text-sm leading-relaxed">{blocks}</div>;
}
