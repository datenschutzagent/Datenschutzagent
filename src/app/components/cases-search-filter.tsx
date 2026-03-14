import { useState } from "react";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Search, X, Filter, Calendar } from "lucide-react";
import { CaseStatus, Priority, statusLabels, priorityLabels } from "../lib/mock-data";

export interface CasesFilters {
  searchQuery: string;
  status: CaseStatus | "all";
  priority: Priority | "all";
  department: string;
  hasDeadline: boolean | null;
  tags: string[];
}

interface CasesSearchFilterProps {
  filters: CasesFilters;
  onFiltersChange: (filters: CasesFilters) => void;
  availableDepartments: string[];
  availableTags: string[];
}

export function CasesSearchFilter({
  filters,
  onFiltersChange,
  availableDepartments,
  availableTags,
}: CasesSearchFilterProps) {
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

  const handleSearchChange = (value: string) => {
    onFiltersChange({ ...filters, searchQuery: value });
  };

  const handleStatusChange = (value: string) => {
    onFiltersChange({ ...filters, status: value as CaseStatus | "all" });
  };

  const handlePriorityChange = (value: string) => {
    onFiltersChange({ ...filters, priority: value as Priority | "all" });
  };

  const handleDepartmentChange = (value: string) => {
    onFiltersChange({ ...filters, department: value });
  };

  const handleTagToggle = (tag: string) => {
    const newTags = filters.tags.includes(tag)
      ? filters.tags.filter(t => t !== tag)
      : [...filters.tags, tag];
    onFiltersChange({ ...filters, tags: newTags });
  };

  const handleDeadlineFilter = (value: string) => {
    const hasDeadline = value === "with" ? true : value === "without" ? false : null;
    onFiltersChange({ ...filters, hasDeadline });
  };

  const clearFilters = () => {
    onFiltersChange({
      searchQuery: "",
      status: "all",
      priority: "all",
      department: "all",
      hasDeadline: null,
      tags: [],
    });
  };

  const hasActiveFilters = 
    filters.searchQuery !== "" ||
    filters.status !== "all" ||
    filters.priority !== "all" ||
    filters.department !== "all" ||
    filters.hasDeadline !== null ||
    filters.tags.length > 0;

  const activeFilterCount = 
    (filters.searchQuery !== "" ? 1 : 0) +
    (filters.status !== "all" ? 1 : 0) +
    (filters.priority !== "all" ? 1 : 0) +
    (filters.department !== "all" ? 1 : 0) +
    (filters.hasDeadline !== null ? 1 : 0) +
    filters.tags.length;

  return (
    <div className="space-y-4">
      {/* Search Bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400 dark:text-slate-500" />
          <Input
            placeholder="Vorgänge durchsuchen (Titel, Antragsteller, Abteilung...)"
            value={filters.searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-10"
          />
          {filters.searchQuery && (
            <button
              onClick={() => handleSearchChange("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300"
              aria-label="Suche leeren"
            >
              <X className="size-4" />
            </button>
          )}
        </div>
        <Popover open={showAdvancedFilters} onOpenChange={setShowAdvancedFilters}>
          <PopoverTrigger asChild>
            <Button variant="outline" className="relative">
              <Filter className="size-4 mr-2" />
              Filter
              {activeFilterCount > 0 && (
                <Badge className="ml-2 size-5 flex items-center justify-center p-0 bg-blue-600">
                  {activeFilterCount}
                </Badge>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-96" align="end">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">Erweiterte Filter</h4>
                {hasActiveFilters && (
                  <Button variant="ghost" size="sm" onClick={clearFilters}>
                    Zurücksetzen
                  </Button>
                )}
              </div>

              {/* Status Filter */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Status</label>
                <Select value={filters.status} onValueChange={handleStatusChange}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Alle Status</SelectItem>
                    {Object.entries(statusLabels).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Priority Filter */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Priorität</label>
                <Select value={filters.priority} onValueChange={handlePriorityChange}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Alle Prioritäten</SelectItem>
                    {Object.entries(priorityLabels).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Department Filter */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Abteilung</label>
                <Select value={filters.department} onValueChange={handleDepartmentChange}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Alle Abteilungen</SelectItem>
                    {availableDepartments.map((dept) => (
                      <SelectItem key={dept} value={dept}>
                        {dept}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Deadline Filter */}
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  <Calendar className="size-4 inline mr-1" />
                  Frist
                </label>
                <Select 
                  value={
                    filters.hasDeadline === true 
                      ? "with" 
                      : filters.hasDeadline === false 
                      ? "without" 
                      : "all"
                  } 
                  onValueChange={handleDeadlineFilter}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Alle</SelectItem>
                    <SelectItem value="with">Mit Frist</SelectItem>
                    <SelectItem value="without">Ohne Frist</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Tags Filter */}
              {availableTags.length > 0 && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">Tags</label>
                  <div className="flex flex-wrap gap-2">
                    {availableTags.map((tag) => (
                      <Badge
                        key={tag}
                        variant={filters.tags.includes(tag) ? "default" : "outline"}
                        className="cursor-pointer"
                        onClick={() => handleTagToggle(tag)}
                      >
                        {tag}
                        {filters.tags.includes(tag) && (
                          <X className="size-3 ml-1" />
                        )}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </PopoverContent>
        </Popover>
      </div>

      {/* Active Filters Display */}
      {hasActiveFilters && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm text-slate-600 dark:text-slate-400">Aktive Filter:</span>
          {filters.status !== "all" && (
            <Badge variant="secondary" className="gap-1">
              Status: {statusLabels[filters.status as CaseStatus]}
              <button
                onClick={() => handleStatusChange("all")}
                className="hover:text-slate-900 dark:hover:text-slate-100"
                aria-label="Status-Filter entfernen"
              >
                <X className="size-3" />
              </button>
            </Badge>
          )}
          {filters.priority !== "all" && (
            <Badge variant="secondary" className="gap-1">
              Priorität: {priorityLabels[filters.priority as Priority]}
              <button
                onClick={() => handlePriorityChange("all")}
                className="hover:text-slate-900 dark:hover:text-slate-100"
                aria-label="Priorität-Filter entfernen"
              >
                <X className="size-3" />
              </button>
            </Badge>
          )}
          {filters.department !== "all" && (
            <Badge variant="secondary" className="gap-1">
              Abteilung: {filters.department}
              <button
                onClick={() => handleDepartmentChange("all")}
                className="hover:text-slate-900 dark:hover:text-slate-100"
                aria-label="Abteilung-Filter entfernen"
              >
                <X className="size-3" />
              </button>
            </Badge>
          )}
          {filters.hasDeadline !== null && (
            <Badge variant="secondary" className="gap-1">
              {filters.hasDeadline ? "Mit Frist" : "Ohne Frist"}
              <button
                onClick={() => handleDeadlineFilter("all")}
                className="hover:text-slate-900 dark:hover:text-slate-100"
                aria-label="Frist-Filter entfernen"
              >
                <X className="size-3" />
              </button>
            </Badge>
          )}
          {filters.tags.map((tag) => (
            <Badge key={tag} variant="secondary" className="gap-1">
              {tag}
              <button
                onClick={() => handleTagToggle(tag)}
                className="hover:text-slate-900 dark:hover:text-slate-100"
                aria-label={`Tag "${tag}" entfernen`}
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            Alle entfernen
          </Button>
        </div>
      )}
    </div>
  );
}
